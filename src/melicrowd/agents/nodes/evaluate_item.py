"""Nó Qwen #2: ``evaluate_item`` — decide adicionar/voltar/sair.

**Arquitetura híbrida (score LLM × amostragem procedural).**

Descoberta de calibração: um LLM em temperatura baixa é um classificador
~determinístico — para o mesmo (produto, persona) ele devolve SEMPRE a mesma
decisão binária. A taxa agregada vira "tudo-ou-nada" (medido: 0%, 90%, 0% em
3 calibrações de prompt; sonda: add 15/15 para produto bom). Não existe
prompt que faça o modelo "sortear a 5,6%": amostrar é trabalho de RNG, não
de linguagem.

Solução — separar **juízo** de **sorteio**:
1. O Qwen devolve apenas ``interest_level`` (0-1) + reasoning — avaliação
   qualitativa CONTÍNUA do produto sob a ótica da persona. Nisso o LLM é bom,
   e o determinismo dele não atrapalha (é um score, não uma moeda).
2. A decisão é amostrada pelo procedural calibrado (~5,6 % de conversão de
   sessão), com o score modulando a probabilidade base por um fator
   **centrado em 1.0**: ``0.4 + 1.2*interest`` → 0.4-1.6×. interest=0.5
   reproduz exatamente a taxa procedural; produto que empolga a persona
   converte até 1.6× mais, produto rejeitado até 0.4× — a média agregada
   permanece na banda 3-8 %.

Propriedade de degradação: se o Qwen falhar/saturar, o fallback devolve
interest neutro (0.5) → fator 1.0 → procedural puro, mesma calibração.
"""
from __future__ import annotations

import random
from typing import Literal

from pydantic import BaseModel, Field

from melicrowd.agents.prompts import EVALUATE_ITEM
from melicrowd.agents.qwen_runner import qwen_trace_fields, run_qwen_node
from melicrowd.agents.state import AgentState, NodeUpdate
from melicrowd.config import settings

#: Teto absoluto da probabilidade de add por produto (mesmo com interesse máximo).
_MAX_ADD_PROB = 0.85


class EvaluateItemScore(BaseModel):
    """Resposta do Qwen: APENAS o score de interesse (sem decisão binária)."""

    interest_level: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class EvaluateItemResponse(BaseModel):
    """Decisão final do nó (amostrada proceduralmente)."""

    decision: Literal["add_to_cart", "back_to_list", "exit"]
    reasoning: str = ""
    interest_level: float = Field(ge=0.0, le=1.0, default=0.5)


def _score_fallback(_state: AgentState) -> EvaluateItemScore:
    """Interest neutro quando Qwen falha — fator ~1.0, calibração intacta.

    0.7 é o CENTRO do fator (média empírica do interest que o LLM devolve),
    não 0.5: devolver 0.5 aqui penalizaria sessões em fallback (fator 0.7).
    """
    return EvaluateItemScore(interest_level=0.7, reasoning="fallback neutro (qwen indisponível)")


def _interest_factor(interest: float) -> float:
    """Mapeia interest 0-1 → fator multiplicativo 0.4-1.6.

    Mapeamento QUADRÁTICO centrado em ~0.7 (``0.4 + 1.2·i²`` → f(0.707)=1.0):
    medição em produção mostrou que o interest do Qwen tem média ~0.7 (catálogo
    com ratings 3.8-4.9), não 0.5 — o mapeamento linear centrado em 0.5
    multiplicava quase tudo por 1.3-1.5× e a conversão de sessão foi a 22%
    (alvo: 3-8%). Centrar o fator na média EMPÍRICA preserva a taxa agregada;
    a forma quadrática ainda pune interesse medíocre e premia o alto.
    """
    i = max(0.0, min(1.0, interest))
    return 0.4 + 1.2 * i * i


def _sample_decision(state: AgentState, *, interest: float | None = None) -> EvaluateItemResponse:
    """Amostra a decisão: procedural calibrado × fator de interesse do LLM.

    Args:
        state: estado do agente (persona, intent, produto atual, budget).
        interest: score 0-1 vindo do Qwen, ou ``None`` para procedural puro
            (equivale a interest neutro 0.5 — fator 1.0).
    """
    p = state.persona
    product = state.current_product
    if product is None:
        # Sem produto carregado, mesmo assim dá uma chance pequena de "add"
        # (cenário: agente clica sem ver detalhe). Mantém o funil vivo.
        if random.random() < 0.05:
            return EvaluateItemResponse(decision="add_to_cart", reasoning="impulse (no product)")
        return EvaluateItemResponse(decision="back_to_list", reasoning="no product loaded")

    # Base por intent — probabilidade POR PRODUTO visto (não por sessão). Como
    # cada sessão vê até 8 produtos, a prob de sessão compõe: 1-(1-p)^k. Estes
    # valores baixos dão conversão de SESSÃO realista (~3-8 %): browse/research
    # quase só olham; compare/purchase convertem moderado. (LLM não consegue
    # produzir essa taxa — ele é tudo-ou-nada — por isso usamos sorteio aqui.)
    intent = state.session_intent.value if state.session_intent else "browse"
    base_prob_add = {
        "purchase": 0.27,   # decidido a comprar; alta conversão de sessão
        "compare": 0.15,
        "research": 0.03,
        "browse": 0.015,    # só passeando — raramente compra por impulso
    }.get(intent, 0.05)

    # Modulação por persona
    if p.price_sensitivity > 0.7 and product.price > (state.budget_brl or 99999) * 0.7:
        base_prob_add *= 0.4  # produto caro p/ persona sensível a preço
    if product.rating < 3.5:
        base_prob_add *= 0.5  # rating ruim derruba interesse
    if product.rating > 4.5 and product.review_count > 500:
        base_prob_add *= 1.4  # social proof forte

    # Modulação pelo score do LLM — fator centrado na média empírica (~0.7)
    # não desloca a taxa agregada, só redistribui (produto bom converte mais,
    # ruim converte menos). Sem score (procedural puro), fator é exatamente 1.0.
    effective_interest = interest if interest is not None else 0.7
    factor = 1.0 if interest is None else _interest_factor(interest)
    prob_add = min(_MAX_ADD_PROB, base_prob_add * factor)

    # Exit explícito (sair da sessão) é raro — produto MUITO ruim + persona
    # impaciente; desinteresse extremo do LLM também habilita o caminho.
    llm_repulsed = interest is not None and interest <= 0.15
    if (
        (product.rating < 3.0 or llm_repulsed)
        and p.abandonment_likelihood > 0.7
        and random.random() < 0.3
    ):
        return EvaluateItemResponse(
            decision="exit",
            reasoning="bad product + impatient persona",
            interest_level=effective_interest,
        )

    decision: Literal["add_to_cart", "back_to_list", "exit"] = (
        "add_to_cart" if random.random() < prob_add else "back_to_list"
    )
    return EvaluateItemResponse(
        decision=decision,
        reasoning=(
            f"sampled intent={intent} base={base_prob_add:.3f} "
            f"interest={effective_interest:.2f} p={prob_add:.3f}"
        ),
        interest_level=effective_interest,
    )


def _fallback(state: AgentState) -> EvaluateItemResponse:
    """Decisão 100% procedural (sem score LLM) — caminho qwen desabilitado."""
    return _sample_decision(state, interest=None)


def _render_prompt(state: AgentState) -> str:
    p = state.persona
    product = state.current_product
    if product is None:
        return "no product"
    return EVALUATE_ITEM.format(
        persona_name=p.name,
        persona_age=p.age,
        income_class=p.income_class.value,
        persona_occupation=p.occupation,
        price_sensitivity=p.price_sensitivity,
        brand_loyalty=p.brand_loyalty,
        purchase_drivers=", ".join(p.purchase_drivers),
        product_title=product.title,
        product_category=product.category,
        product_price=product.price,
        product_brand=product.brand,
        product_rating=product.rating,
        product_review_count=product.review_count,
        session_intent=state.session_intent.value if state.session_intent else "browse",
        budget_brl=state.budget_brl or 0,
        cart_summary=", ".join(item.title for item in state.cart) or "vazio",
        cart_total=state.cart_total(),
    )


async def run(state: AgentState) -> NodeUpdate:
    """Executa o nó híbrido.

    Com ``qwen_evaluate_item_enabled=true`` (default): Qwen pontua o interesse
    (juízo qualitativo, com orçamento de chamadas por sessão — ver abaixo) e o
    procedural amostra a decisão (taxa calibrada). Com ``false``: procedural
    puro com fator 1.0 — mesma calibração, zero custo LLM.
    """
    if state.current_product is None:
        return {"current_page": "evaluate_item", "last_evaluation": "back_to_list"}

    # Orçamento de LLM por sessão: pontuar TODO produto visto (até 8) com 50
    # workers saturou o Ollama (691 evaluate em 17 min; decide_session p95 foi
    # a 247s de fila). O score só muda materialmente a decisão onde a prob base
    # é relevante — browse (base 1.5%) não precisa de juízo do LLM. Política:
    # Qwen nos 3 primeiros produtos de sessões research/compare/purchase;
    # o restante usa o procedural calibrado (fator 1.0).
    intent_value = state.session_intent.value if state.session_intent else "browse"
    use_qwen = (
        settings.qwen_evaluate_item_enabled
        and intent_value in ("research", "compare", "purchase")
        and len(state.viewed_products) <= 3
    )

    interest: float | None = None
    if use_qwen:
        score = await run_qwen_node(
            state=state,
            node_name="evaluate_item",
            prompt=_render_prompt(state),
            response_model=EvaluateItemScore,
            fallback=_score_fallback,
            max_output_tokens=settings.qwen_decision_max_tokens,
        )
        interest = score.interest_level

    response = _sample_decision(state, interest=interest)
    return {
        **qwen_trace_fields(state),
        "current_page": "evaluate_item",
        "last_evaluation": response.decision,
    }

"""Tech Lead Agent — gera tarefas reais pro dev e valida entregas.

Persona: Rafael Mendoza (Tech Lead Senior do Mercado Livre, fictício mas
plausível). LLM: DeepSeek-V4-pro via API.

Loop:
    1. Tech Lead gera 1-3 tasks/dia baseado no backlog blueprint.
    2. Cada task tem ``acceptance_criteria`` — lista de checks objetivos
       (HTTP, DB, métrica Prometheus, padrão git, suite de teste).
    3. Willian implementa e marca status=review.
    4. Auto-evaluator roda os checks a cada N min.
    5. Se 100% passa → status=done. Senão → feedback parcial + status=blocked.

Custo médio: ~$0.04/dia (geração + avaliação combinadas) com Deepseek V4 Pro.
"""

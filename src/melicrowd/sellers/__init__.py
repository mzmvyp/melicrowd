"""Camada de agentes vendedores (SELLER).

Diferente dos agentes buyer (que rodam um grafo LangGraph de 14 nós),
sellers seguem um loop procedural mais simples: ciclos de ~30s-2min com
intervalos de 5-30min entre eles. Cada ciclo executa um subconjunto das
seguintes ações:

- ``audit_inventory``: lista produtos do vendedor
- ``check_notifications``: lê alertas de estoque baixo (vindos do stock-monitor)
- ``restock``: incrementa estoque de produtos baixos (PATCH /products/{id}/stock)
- ``suspend``: remove produto sem estoque que o vendedor decide descontinuar
- ``create_product``: cria novo produto (Qwen gera title + description)
- ``update_price``: ajusta preço esporadicamente (PUT /products/{id})

Qwen é usado em 3 pontos: decidir o foco da sessão, avaliar cada notificação
(responder vs ignorar) e gerar texto livre do novo produto.
"""

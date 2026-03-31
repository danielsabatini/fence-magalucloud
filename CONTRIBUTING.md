# Contribuindo — fence_magalucloud

---

## Configurar o ambiente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Executar os testes unitários

```bash
.venv/bin/pytest tests/unit/ -v
```

---

## Testes manuais (desenvolvimento local)

Consulte [TESTING.md](TESTING.md) Fase 1 para os testes locais com `uv run`.

---

## Pipeline de qualidade obrigatório

Ver contrato completo em [CONTRACT.md](CONTRACT.md).

```bash
.venv/bin/ruff format . && .venv/bin/ruff check --fix . && .venv/bin/pyright
```

Saída esperada:

```
1 file left unchanged
All checks passed!
0 errors, 0 warnings, 0 informations
```

O pipeline deve passar sem erros antes de abrir um pull request.

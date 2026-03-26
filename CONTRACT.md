# Contrato de Qualidade de Código

Todo código entregue neste repositório deve passar pelos três verificadores abaixo,
**nesta ordem**, antes de ser commitado ou revisado.

---

## Pipeline obrigatório

```bash
# 1. Formata o código conforme o estilo do projeto
.venv/bin/ruff format .

# 2. Aplica correções automáticas de linting
.venv/bin/ruff check --fix .

# 3. Verifica tipos estaticamente
.venv/bin/pyright
```

Os três comandos devem terminar **sem erros**.

---

## Ferramentas e configuração

| Ferramenta | Versão mínima | Configuração |
|---|---|---|
| [Ruff](https://docs.astral.sh/ruff/) | `>=0.4` | `[tool.ruff]` em `pyproject.toml` |
| [Pyright](https://github.com/microsoft/pyright) | `>=1.1` | `[tool.pyright]` em `pyproject.toml` |

### Regras ativas do Ruff

Selecionadas via `select` em `pyproject.toml`:

| Prefixo | Conjunto |
|---|---|
| `E`, `W` | pycodestyle — erros e avisos de estilo |
| `F` | Pyflakes — variáveis não usadas, imports ausentes |
| `I` | isort — ordenação de imports |
| `PL` | Pylint — boas práticas gerais |
| `PT` | flake8-pytest-style — convenções de teste |

Exceções configuradas:
- `PLR0913` ignorado globalmente (número de parâmetros em funções da lib `fencing`)
- `PLR2004`, `PT012` ignorados em `tests/unit/`
- `PLR2004`, `PT011` ignorados em `tests/integration/`
- `src/fence_magalucloud/fencing.py` excluído do lint (arquivo externo do ClusterLabs)

### Quote style

Aspas simples (`'`) em todo o código Python, conforme `quote-style = "single"`.

---

## Regras de qualidade que o pipeline garante

1. **Sem magic numbers** — use constantes nomeadas (`HTTP_NOT_FOUND = 404`)
2. **Imports ordenados** — `isort` aplicado automaticamente pelo `ruff format`
3. **Sem imports não utilizados** — detectados pelo Pyflakes (`F401`)
4. **Tipos consistentes** — Pyright em modo `basic` cobre anotações de funções públicas
5. **Estilo uniforme** — formatação não negociável via `ruff format`

---

## Arquivos excluídos da verificação

```
fencing.py          # biblioteca externa do ClusterLabs — não modificar
build/
dist/
__pycache__/
*.egg-info/
.venv/
```

---

## Executar tudo de uma vez (atalho)

```bash
.venv/bin/ruff format . && .venv/bin/ruff check --fix . && .venv/bin/pyright
```

Saída esperada quando tudo está correto:

```
1 file left unchanged
All checks passed!
0 errors, 0 warnings, 0 informations
```

---

## Análise estática com SonarQube

### Executar o scanner

```bash
source .env && sonar-scanner
```

### Validação de Aprovação do Quality Gate

```bash
curl -s -u $SONAR_TOKEN: "http://localhost:9000/api/qualitygates/project_status?projectKey=ecloud-platform" | jq .projectStatus.status
```

### Inspeção detalhada de violações (ex: CODE_SMELL)

```bash
curl -s -u $SONAR_TOKEN: "http://localhost:9000/api/issues/search?componentKeys=ecloud-platform&types=CODE_SMELL" | jq .
```

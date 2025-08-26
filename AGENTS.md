# AGENTS

Este repositório contém o projeto **Disparador de Avisos de Ponto via WhatsApp**.

## Configuração do ambiente

- Utilize Python 3.9 ou superior.
- Crie e ative um ambiente virtual (`python -m venv .venv && source .venv/bin/activate`).
- Instale as dependências com `pip install -r requirements.txt`.
- Copie `.env.example` para `.env` e ajuste as variáveis necessárias (nunca versione `.env`).

## Diretrizes de desenvolvimento

- Siga o padrão [PEP 8](https://peps.python.org/pep-0008/) e utilize `flake8` para verificação de estilo quando disponível.
- Escreva docstrings e comentários seguindo o [PEP 257](https://peps.python.org/pep-0257/).
- Utilize type hints sempre que possível.
- Mantenha funções e classes pequenas e coesas.
- Mantenha o código e a documentação em português claro.

## Fluxo de validação

Antes de enviar alterações:

1. Execute `pytest` e garanta que todos os testes passam.
2. Execute `flake8` e corrija eventuais avisos.
3. Atualize ou crie testes e documentação para qualquer mudança de comportamento.

## Convenções de commit

- Mensagens em português, no modo imperativo e descritivo.
- Utilize prefixos semânticos quando fizer sentido:
  - `feat:` nova funcionalidade
  - `fix:` correção de bug
  - `docs:` alterações na documentação
  - `refactor:` refatoração sem mudança de comportamento
  - `test:` adição ou ajuste de testes
  - `chore:` manutenção geral
- Commits pequenos e focados em uma única mudança.

## Organização de branches

- Crie branches específicas para cada tarefa (`feat/...`, `fix/...`, etc.).
- Solicite revisão via Pull Request antes do merge.

## Outros cuidados

- Não versione segredos: mantenha-os apenas em `.env`.
- Nomeie variáveis, funções e arquivos de forma clara.
- Garanta que os arquivos estejam em UTF-8 e terminem com newline.

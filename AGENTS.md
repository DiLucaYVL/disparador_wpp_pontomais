# AGENTS

Este repositório contém o projeto **Disparador de Avisos de Ponto via WhatsApp**.

## Configuração do ambiente

- Utilize Python 3.11 ou superior (a imagem Docker oficial usa `python:3.11-slim`).
- Crie um ambiente virtual com `python -m venv .venv` e ative-o antes de qualquer comando (`source .venv/bin/activate` no Linux/macOS ou `.\.venv\Scripts\activate` no Windows).
- Instale as dependências com `pip install -r requirements.txt` e sempre adicione novas bibliotecas dentro do `.venv`.
- Sempre que instalar ou atualizar uma dependência, atualize o `requirements.txt` (por exemplo, `pip freeze > requirements.txt`).
- Copie `.env.example` para `.env` e ajuste as variáveis necessárias (nunca versione `.env`).

## Estrutura do projeto

```
disparador_wpp_pontomais/
├── main.py                      # Entrypoint Flask (porta 8000)
├── gunicorn.conf.py             # Config do Gunicorn (gthread, timeout 600s)
├── requirements.txt
├── Dockerfile                   # python:3.11-slim
├── docker-compose.yml
├── app/
│   ├── routes.py                # Blueprint Flask: todos os endpoints da API
│   ├── controller.py            # Orquestração do fluxo de processamento
│   ├── tasks.py                 # Fila assíncrona com ThreadPoolExecutor
│   ├── history.py               # Histórico de envios (MySQL)
│   ├── history_export.py        # Exportação do histórico para Excel
│   ├── types.py                 # TypedDicts compartilhados
│   ├── config/
│   │   └── settings.py          # Leitura centralizada de variáveis de ambiente
│   ├── processamento/
│   │   ├── csv_reader.py        # Parser: relatório de Auditoria
│   │   ├── csv_reader_ocorrencias.py   # Parser: relatório de Ocorrências
│   │   ├── csv_reader_assinaturas.py   # Parser: relatório de Assinaturas
│   │   ├── mapear_gerencia.py   # Normalização de nomes de equipes
│   │   ├── ocorrencias_processor.py    # Lógica de mensagens para Ocorrências
│   │   ├── motivos_ocorrencias.py      # Mapeamento de motivos
│   │   └── log.py               # Helpers de logging
│   ├── whatsapp/
│   │   ├── mensagem.py          # Templates TEMPLATES e geração de msgs (Auditoria)
│   │   ├── mensagem_assinaturas.py     # Templates para Assinaturas
│   │   └── numeros_equipes.py   # Resolução do número WPP por equipe
│   └── services/
│       ├── google_sheets.py     # Integração Google Sheets API
│       └── email_sender.py      # Envio de logs via SMTP
├── templates/                   # Templates Jinja2 (index.html, historico.html)
├── static/                      # Assets estáticos (JS, CSS)
├── uploads/                     # CSVs temporários (limpos após processamento)
├── log/                         # Arquivos de log de execução
├── task_status/                 # JSONs de status das tarefas assíncronas
└── secrets/                     # Credenciais (montado como volume read-only)
```

## Tipos de relatório suportados

| Tipo         | Parser                          | Gerador de mensagens          |
|--------------|---------------------------------|-------------------------------|
| Auditoria    | `csv_reader.py`                 | `mensagem.py` (TEMPLATES)     |
| Ocorrências  | `csv_reader_ocorrencias.py`     | `ocorrencias_processor.py`    |
| Assinaturas  | `csv_reader_assinaturas.py`     | `mensagem_assinaturas.py`     |

## Diretrizes de desenvolvimento

- Siga o padrão [PEP 8](https://peps.python.org/pep-0008/) e utilize `flake8` para verificação de estilo quando disponível.
- Escreva docstrings e comentários seguindo o [PEP 257](https://peps.python.org/pep-0257/).
- Utilize type hints sempre que possível.
- Mantenha funções e classes pequenas e coesas.
- Mantenha o código e a documentação em português claro.
- **Nunca use `time.sleep()` no fluxo de envio assíncrono** — use delays controlados apenas dentro da função `enviar_whatsapp` (anti-spam).

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

- Não versione segredos: mantenha-os apenas em `.env` ou no volume `secrets/`.
- Nomeie variáveis, funções e arquivos de forma clara.
- Garanta que os arquivos estejam em UTF-8 e terminem com newline.

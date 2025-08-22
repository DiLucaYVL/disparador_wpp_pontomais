import multiprocessing

# Endereço/porta
bind = "0.0.0.0:8000"

# Workers: fórmula padrão recomendada (CPU-bound)
workers = multiprocessing.cpu_count() * 2 + 1

# ► Se sua app for mais I/O-bound (muitas chamadas externas),
#    você pode habilitar threads. Descomente as duas linhas abaixo:
# worker_class = "gthread"   # usa threads por worker
# threads = 2                # 2-4 é um bom começo

# ► Se sua app for ASGI (FastAPI/Starlette) e você quiser usar uvicorn:
# from uvicorn.workers import UvicornWorker
# worker_class = "uvicorn.workers.UvicornWorker"

# Tempo máximo que um worker pode levar para responder (mata e recria)
timeout = 120

# Tempo para shutdown gracioso antes de forçar kill (default=30)
graceful_timeout = 30

# Mantém conexões HTTP ativas (keep-alive) por alguns segundos
keepalive = 5

# Estabilidade em long running: recicla workers periodicamente
max_requests = 1000
max_requests_jitter = 50

# Logs (enviados ao journal do systemd)
accesslog = "-"   # stdout
errorlog = "-"    # stderr
loglevel = "info"

# Opcional: pré-carrega a app antes de forkar os workers (pode reduzir memória)
# Cuidado: se você abrir conexões (DB/Redis) no import, use hooks p/ reabrir por worker
# preload_app = True

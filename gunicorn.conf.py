import multiprocessing

# Escuta em todas as interfaces na porta 8000
bind = "0.0.0.0:8000"

# Workers (processos)
workers = multiprocessing.cpu_count() * 2 + 1

# Classe de worker para I/O bound
worker_class = "gthread"

# Threads por worker (ajuste conforme a carga do servidor)
threads = 8   # pode subir para 16 se tiver muita espera por I/O

# Tempo máximo que uma request pode levar antes de matar o worker
timeout = 600             # 10 minutos
graceful_timeout = 60     # tempo de espera antes de forçar kill

# Mantém conexões HTTP vivas por alguns segundos
keepalive = 5

# Recicla workers periodicamente para evitar vazamento de memória
max_requests = 2000
max_requests_jitter = 200

# Logs (mandados para stdout/stderr → visíveis via journalctl)
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Opcional: usar memória compartilhada para arquivos temporários
# worker_tmp_dir = "/dev/shm"

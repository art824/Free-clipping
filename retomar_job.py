#!/usr/bin/env python3
"""retomar_job.py - quando o auto.py foi fechado com um video ainda processando.

Espera aquele job terminar no OpenShorts, organiza (horario de Brasilia +
YouTube automatico), marca o link/arquivo como feito e depois segue a fila
normal do auto.py.

Uso:
    python retomar_job.py <job_id> <conta> [link_ou_arquivo_original]
"""

import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
import auto        # noqa: E402  (log, esperar, marcar, manter_acordado; poe openshorts/ no path)
import organizar   # noqa: E402


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    job, conta = sys.argv[1], sys.argv[2]
    origem = sys.argv[3] if len(sys.argv) > 3 else None

    if not auto.api_ok():
        print("O OpenShorts nao esta rodando. Abra o ABRIR DOCKER.bat primeiro.")
        return 1

    auto.manter_acordado(True)
    try:
        auto.log(f"=== retomando job {job} ({conta}) ===")
        if auto.esperar(job):
            r = organizar.organizar(job, conta)
            auto.log(f"  OK: {r.get('copiados', 0)} clipes -> {r.get('destino')}"
                     f"  (YouTube automatico: {r.get('drive', 0)})")
            sucesso = bool(r.get("ok"))
        else:
            auto.log("  job nao terminou bem")
            sucesso = False
        if origem:
            tipo = "url" if origem.startswith("http") else "arquivo"
            auto.marcar(conta, (tipo, origem), sucesso)
    finally:
        auto.manter_acordado(False)

    auto.log("=== seguindo a fila normal ===")
    return auto.main()


if __name__ == "__main__":
    sys.exit(main())

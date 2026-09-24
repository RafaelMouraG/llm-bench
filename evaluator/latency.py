#!/usr/bin/env python3
"""Diagnóstico de latência (RNF11, M16) de uma entrega congelada do encurtador.

Uso: python3 evaluator/latency.py ENTREGA [--out DIR] [--label NOME] [--config ARQ]

Não é aceitação: não produz veredito nem altera A_i. Reaproveita de evaluate.py o
ambiente limpo (container novo, build com rede só para os registros, servidor sem
rede, DATA_DIR em tmpfs) e mede, com um gerador de carga em Go (evaluator/loadgen)
num container cliente na mesma rede interna:

  GET /{code}       sobre links semeados antes da medição; válido = 302 e Location igual à url
  POST /api/links   sem alias; válido = 201 com objeto JSON e code

Para cada operação e nível de concorrência (malha fechada): aquecimento descartado,
número fixo de requisições medidas, percentis p50/p90/p95/p99 só das respostas
válidas, vazão e taxa de erro (respostas fora do contrato e erros de transporte).
Servidor e cliente ficam em conjuntos de CPUs distintos. O perfil de carga está em
evaluator/config.json, seção rnf11_perfil_carga, e é provisório.

Entrega que não compila ou não fica pronta fica sem M16 (ausente, sem valor).
Saída: result.json e summary.txt em .pilot/latency/<run_id>/ (padrão).
Código de saída: 0 medição completa; 1 M16 ausente (entrega não iniciou);
2 falha do instrumento ou erro de uso.
"""
import argparse
import hashlib
import json
import os
import platform
import secrets
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate as ev  # noqa: E402

TOOL_VERSION = "0.1.0"
PREFIX = "llmbench-lat-"
LOADGEN_SRC = HERE / "loadgen" / "main.go"
OPS = ("redirect", "create")


def loadgen_binary(image, image_id):
    """Compila o gerador de carga uma vez por fonte e imagem, num container sem rede."""
    src = LOADGEN_SRC.read_bytes()
    key = hashlib.sha256(src + image_id.encode()).hexdigest()[:16]
    path = ev.ROOT / ".pilot" / "latency" / "bin" / f"loadgen-{key}"
    if path.exists():
        return path, key
    path.parent.mkdir(parents=True, exist_ok=True)
    name = f"{PREFIX}build-{secrets.token_hex(3)}"
    script = ("mkdir -p /tmp/src && cat > /tmp/src/main.go && cd /tmp/src && "
              "go build -trimpath -o /tmp/loadgen main.go >&2 && cat /tmp/loadgen")
    try:
        r = ev.docker("run", "--rm", "-i", "--name", name, "--network", "none", "--read-only", "--cap-drop", "ALL",
                      "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,exec,size=1g", "-u", "1001",
                      "-e", "HOME=/tmp", "-e", "GOCACHE=/tmp/gocache", "-e", "GOTOOLCHAIN=local", "-e", "CGO_ENABLED=0",
                      image, "sh", "-c", script, input=src, binary=True, timeout=600, check=False)
    finally:
        ev.docker("rm", "-f", name, check=False)
    if r.returncode or not r.stdout:
        raise ev.EvaluatorError(f"compilação do gerador de carga falhou ({r.returncode}): {r.stderr.decode(errors='replace')[-800:]}")
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(r.stdout)
    tmp.chmod(0o755)
    tmp.rename(path)
    return path, key


class LatencyRun(ev.Run):
    def __init__(self, delivery, out_dir, raw_cfg, cfg, label):
        super().__init__(delivery, out_dir, raw_cfg, cfg, label)
        self.base = PREFIX + self.run_id.lower()
        self.net, self.proxy, self.app, self.client = (f"{self.base}-{s}" for s in ("net", "proxy", "app", "client"))
        self.profile = raw_cfg["rnf11_perfil_carga"]
        self.measurements = []
        self.status = None

    def cleanup(self):
        codes = {}
        for name in (self.client, self.app, self.proxy):
            codes[name] = ev.docker("rm", "-f", "-v", name, check=False).returncode
        codes[self.net] = ev.docker("network", "rm", self.net, check=False).returncode
        left = ev.docker("ps", "-a", "--filter", f"name={self.base}", "--format", "{{.Names}}", check=False).stdout.split()
        left += ev.docker("network", "ls", "--filter", f"name={self.base}", "--format", "{{.Name}}", check=False).stdout.split()
        return {"exit_codes": codes, "leftover": left}

    def loadgen(self, op, concurrency, warmup, requests, codes=None, urls=None):
        params = {"host": ev.APP_ALIAS, "port": 8080, "op": op, "concurrency": concurrency, "warmup": warmup,
                  "requests": requests, "codes": codes or [], "urls": urls or [],
                  "timeout_ms": self.profile["request_timeout_ms"], "tag": self.run_id.lower()}
        r = ev.docker("exec", "-i", self.client, "/tmp/loadgen", input=json.dumps(params),
                      timeout=self.profile["phase_timeout_seconds"], check=False)
        if r.returncode:
            raise ev.EvaluatorError(f"loadgen {op} c={concurrency} falhou ({r.returncode}): {r.stderr[-800:]}")
        return json.loads(r.stdout)

    def alive(self):
        return self.client_call("ready", {"host": ev.APP_ALIAS, "port": 8080}, 3, timeout=30)["ready"]

    def execute(self, loadgen_path):
        tar_bytes, tree_hash, count, deps = ev.pack_delivery(self.delivery)
        self.diag["delivery"] = {"path": str(self.delivery), "tree_sha256": tree_hash, "entries": count}
        self.diag["dependencies"] = deps
        self.setup(tar_bytes)
        if not self.build():
            self.status = "ausente: build.sh falhou (" + self.req["RNF01"]["summary"] + ")"
            return
        prof = self.profile
        ev.docker("update", "--cpuset-cpus", prof["app_cpuset"], self.app)
        r = self.res
        ev.docker("run", "-d", "--name", self.client, "--network", self.net,
                  *self.hardening(r["client_memory"], prof["client_cpus"], 512), "--cpuset-cpus", prof["client_cpuset"],
                  "--sysctl", "net.ipv4.ip_local_port_range=1024 65535", "--sysctl", "net.ipv4.tcp_tw_reuse=1",
                  "--tmpfs", "/tmp:rw,nosuid,nodev,exec,size=64m", self.image, "sleep", "infinity")
        ev.docker("exec", "-i", self.client, "sh", "-c", "cat > /tmp/checks.py", input=(HERE / "checks.py").read_text())
        ev.docker("exec", "-i", self.client, "sh", "-c", "cat > /tmp/loadgen && chmod 755 /tmp/loadgen",
                  input=loadgen_path.read_bytes(), binary=True)

        s1 = self.start(1)
        self.diag["start"] = s1
        if not s1["ready"]:
            self.status = f"ausente: GET /health não respondeu 200 {self.not_ready(s1)}"
            self.stop(1)
            return
        seed = self.loadgen("seed", 4, 0, prof["seed_links"])
        codes, urls = seed["codes"], seed["urls"]
        self.diag["seed"] = {"links": len(codes)}
        for op in OPS:
            spec = prof[op]
            for c in prof["concurrency"]:
                if not self.alive():
                    self.measurements.append({"op": op, "concurrency": c, "skipped": "servidor indisponível antes da fase"})
                    continue
                t0 = time.monotonic()
                m = self.loadgen(op, c, spec["warmup_requests"], spec["requests"], codes, urls)
                m["phase_seconds"] = round(time.monotonic() - t0, 2)
                self.measurements.append(m)
            if op == "redirect":
                # Sanidade: cada 302 válido (aquecimento incluído) deve ter somado uma visita (RNF06).
                expected = sum(x.get("valid", 0) + x.get("warmup_valid", 0) for x in self.measurements if x["op"] == "redirect")
                observed = self.loadgen("visits", 8, 0, 1, codes, urls).get("visits_total")
                self.diag["visits_check"] = {"expected_from_valid_302": expected, "observed_sum": observed,
                                             "ok": observed == expected}
        self.diag["alive_after"] = self.alive()
        self.stop(1)
        self.status = "completa"

    def run(self):
        self.out.mkdir(parents=True, exist_ok=True)
        started_at, t0 = ev.utc_now(), time.monotonic()
        info = json.loads(ev.docker("image", "inspect", self.image).stdout)[0]
        self.diag["image_id"] = info["Id"]
        loadgen_key = None
        try:
            loadgen_path, loadgen_key = loadgen_binary(self.image, info["Id"])
            self.execute(loadgen_path)
        except Exception as e:  # noqa: BLE001 — falha do instrumento, nunca atribuída à entrega
            self.errors.append(f"{type(e).__name__}: {str(e)[:600]}")
        except KeyboardInterrupt:
            self.errors.append("interrompido pelo usuário")
        finally:
            try:
                self.collect_logs()
            except Exception as e:  # noqa: BLE001
                self.errors.append(f"coleta de logs: {e}")
            cleanup = self.cleanup()
        if self.errors:
            self.status = "inconclusiva (falha do instrumento)"
        result = {
            "schema": "llm-bench-latency/0.1", "tool_version": TOOL_VERSION, "requirement": "RNF11", "metric": "M16",
            "acceptance": "não — diagnóstico; não altera A_i",
            "run_id": self.run_id, "label": self.label, "status": self.status,
            "started_at_utc": started_at, "finished_at_utc": ev.utc_now(),
            "duration_seconds": round(time.monotonic() - t0, 2),
            "image": self.image, "profile": self.profile, "loadgen": {"source": "evaluator/loadgen/main.go", "key": loadgen_key},
            "placement": {"app_cpus": self.res["app_cpus"], "app_memory": self.res["app_memory"],
                          "app_cpuset": self.profile["app_cpuset"], "client_cpuset": self.profile["client_cpuset"],
                          "host_cpus": os.cpu_count(), "host_kernel": platform.release()},
            "base_url": self.base_url,
            "measurements": self.measurements,
            "diagnostics": self.diag, "errors": self.errors, "cleanup": cleanup,
        }
        (self.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        summary = render(result)
        (self.out / "summary.txt").write_text(summary)
        return result, summary


def render(result):
    d = result["diagnostics"]
    lines = [f"Latência {result['run_id']} ({result['label']}) — {result['status']}",
             f"Entrega: árvore sha256 {d.get('delivery', {}).get('tree_sha256', '?')[:16]}…  "
             f"build {d.get('build', {}).get('seconds', '?')} s  prontidão {d.get('start', {}).get('seconds', '?')} s",
             f"Servidor: CPUs {result['placement']['app_cpuset']} ({result['placement']['app_cpus']}), "
             f"cliente: CPUs {result['placement']['client_cpuset']}; perfil provisório (rnf11_perfil_carga)", "",
             f"{'operação':<9} {'conc':>4} {'válidas':>8} {'erro':>7} {'p50 ms':>8} {'p90 ms':>8} {'p95 ms':>8} "
             f"{'p99 ms':>8} {'máx ms':>8} {'req/s':>9}"]
    for m in result["measurements"]:
        if "skipped" in m:
            lines.append(f"{m['op']:<9} {m['concurrency']:>4}  pulada: {m['skipped']}")
            continue
        lat = m.get("latency_ms") or {}
        cell = lambda k: f"{lat[k]:>8.2f}" if k in lat else f"{'—':>8}"  # noqa: E731
        lines.append(f"{m['op']:<9} {m['concurrency']:>4} {m['valid']:>8} {m['error_rate']:>7.2%} {cell('p50')} {cell('p90')} "
                     f"{cell('p95')} {cell('p99')} {cell('max')} {m['throughput_valid_rps']:>9.1f}")
        if m.get("invalid_samples"):
            lines.append(f"          exemplos fora do contrato: {m['invalid_samples'][:2]}")
    vc = d.get("visits_check")
    if vc:
        lines += ["", f"Sanidade: visitas somadas {vc['observed_sum']} para {vc['expected_from_valid_302']} redirecionamentos 302 válidos"
                  + (" — ok" if vc["ok"] else " — DIVERGE")]
    if result["errors"]:
        lines += ["", "Falhas do instrumento:"] + ["  " + e[:300] for e in result["errors"]]
    left = result["cleanup"]["leftover"]
    lines += ["", "Limpeza: " + ("ok, nada restou com o prefixo " + PREFIX if not left else "SOBRARAM " + ", ".join(left))]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("delivery", help="diretório ou tar da entrega congelada")
    parser.add_argument("--config", default=str(HERE / "config.json"))
    parser.add_argument("--out", help="diretório de saída (padrão: .pilot/latency/<run_id>)")
    parser.add_argument("--label", help="rótulo livre registrado no resultado")
    parser.add_argument("--quiet", action="store_true", help="não imprime o resumo")
    args = parser.parse_args(argv)
    if not Path(args.delivery).exists():
        parser.error(f"entrega não encontrada: {args.delivery}")
    raw_cfg, cfg = ev.load_config(args.config)
    if "rnf11_perfil_carga" not in raw_cfg:
        parser.error("configuração sem a seção rnf11_perfil_carga")
    run = LatencyRun(args.delivery, ".", raw_cfg, cfg, args.label or Path(args.delivery).name)
    run.out = Path(args.out) if args.out else ev.ROOT / ".pilot" / "latency" / run.run_id
    result, summary = run.run()
    if not args.quiet:
        print(summary, end="")
        print("Evidências:", run.out)
    if result["status"] == "completa":
        return 0
    return 1 if (result["status"] or "").startswith("ausente") else 2


if __name__ == "__main__":
    sys.exit(main())

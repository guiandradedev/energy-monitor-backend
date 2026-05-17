"""Smoke test do endpoint /api/telemetry — valida o filtro com todos os
operadores usando o valor exibido (3 casas) de linhas reais."""
import sys
import urllib.parse
import urllib.request
import json
import random
from datetime import datetime, timedelta, timezone

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8002"
FIELDS = ["rms_sct1", "rms_sct2", "rms_zmpt1", "rms_zmpt2"]


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.load(r)


def assert_(cond, msg):
    if not cond:
        print(f"  ✗ {msg}")
        return False
    print(f"  ✓ {msg}")
    return True


def fmt(v):
    return f"{v:.3f}"


def test_eq_with_displayed_values():
    print("\n[1] eq usando valor exibido (3 casas) deve achar ao menos uma linha")
    sample = get("/api/telemetry?limit=5")
    failures = 0
    for row in sample["data"]:
        for field in FIELDS:
            displayed = fmt(row[field])
            qs = urllib.parse.urlencode({"field": field, "op": "eq", "value": displayed})
            r = get(f"/api/telemetry?{qs}&limit=1")
            ok = assert_(r["total"] >= 1, f"{field}={displayed} → total={r['total']}")
            if not ok:
                failures += 1
    return failures


def test_inequalities():
    print("\n[2] lt/lte/gt/gte coerentes (lt deve dar < que gt, lte+gt cobrem o universo)")
    failures = 0
    sample = get("/api/telemetry?limit=1")
    row = sample["data"][0]
    field = "rms_sct1"
    val = fmt(row[field])
    base_total = get(f"/api/telemetry?limit=1").get("total", 0)
    qs_lt = urllib.parse.urlencode({"field": field, "op": "lt", "value": val})
    qs_gt = urllib.parse.urlencode({"field": field, "op": "gt", "value": val})
    qs_eq = urllib.parse.urlencode({"field": field, "op": "eq", "value": val})
    n_lt = get(f"/api/telemetry?{qs_lt}&limit=1")["total"]
    n_gt = get(f"/api/telemetry?{qs_gt}&limit=1")["total"]
    n_eq = get(f"/api/telemetry?{qs_eq}&limit=1")["total"]
    print(f"  janela base: {base_total} linhas")
    print(f"  {field} < {val} → {n_lt}")
    print(f"  {field} = {val} → {n_eq}")
    print(f"  {field} > {val} → {n_gt}")
    failures += int(not assert_(n_lt + n_eq + n_gt == base_total, f"lt+eq+gt deve cobrir o total: {n_lt}+{n_eq}+{n_gt}={n_lt+n_eq+n_gt} vs {base_total}"))
    qs_lte = urllib.parse.urlencode({"field": field, "op": "lte", "value": val})
    qs_gte = urllib.parse.urlencode({"field": field, "op": "gte", "value": val})
    n_lte = get(f"/api/telemetry?{qs_lte}&limit=1")["total"]
    n_gte = get(f"/api/telemetry?{qs_gte}&limit=1")["total"]
    failures += int(not assert_(n_lte == n_lt + n_eq, f"lte = lt + eq: {n_lte} == {n_lt}+{n_eq}"))
    failures += int(not assert_(n_gte == n_gt + n_eq, f"gte = gt + eq: {n_gte} == {n_gt}+{n_eq}"))
    return failures


def test_date_range():
    print("\n[3] filtro de data limita corretamente")
    failures = 0
    to = datetime.now(timezone.utc)
    from_short = to - timedelta(minutes=10)
    from_long = to - timedelta(days=20)
    qs_short = urllib.parse.urlencode({"from": from_short.isoformat(), "to": to.isoformat()})
    qs_long = urllib.parse.urlencode({"from": from_long.isoformat(), "to": to.isoformat()})
    n_short = get(f"/api/telemetry?{qs_short}&limit=1")["total"]
    n_long = get(f"/api/telemetry?{qs_long}&limit=1")["total"]
    print(f"  últimos 10 min: {n_short}")
    print(f"  últimos 20 dias: {n_long}")
    failures += int(not assert_(n_long > n_short, "janela maior deve ter ≥ amostras que janela menor"))
    failures += int(not assert_(n_long >= 1_500_000, f"janela de 20d deve ter ~1.7M (got {n_long})"))
    return failures


def test_csv_export_with_filter():
    print("\n[4] /export.csv respeita o filtro (cabeçalho + N linhas)")
    failures = 0
    sample = get("/api/telemetry?limit=1")
    row = sample["data"][0]
    field = "rms_sct1"
    val = fmt(row[field])
    qs = urllib.parse.urlencode({"field": field, "op": "eq", "value": val})
    csv_url = f"{BASE}/api/telemetry/export.csv?{qs}"
    with urllib.request.urlopen(csv_url, timeout=30) as r:
        body = r.read().decode("utf-8")
    lines = body.strip().split("\n")
    header = lines[0]
    failures += int(not assert_(header == "timestamp,breaker_id,rms_sct1,rms_sct2,rms_zmpt1,rms_zmpt2", f"header ok: {header}"))
    json_count = get(f"/api/telemetry?{qs}&limit=1")["total"]
    csv_rows = len(lines) - 1
    failures += int(not assert_(csv_rows == json_count, f"CSV rows ({csv_rows}) == json total ({json_count})"))
    return failures


def test_error_cases():
    print("\n[5] erros de validação")
    failures = 0
    for path, expect in [
        ("/api/telemetry?field=rms_sct1", "field, op e value"),
        ("/api/telemetry?field=foo&op=eq&value=1", "field inválido"),
        ("/api/telemetry?field=rms_sct1&op=xx&value=1", "op inválido"),
        ("/api/telemetry?field=rms_sct1&op=eq&value=abc", "value deve ser numérico"),
        ("/api/telemetry?from=blah", "from inválido"),
    ]:
        try:
            urllib.request.urlopen(BASE + path, timeout=5)
            failures += 1
            print(f"  ✗ esperava 400 em {path}")
        except urllib.error.HTTPError as e:
            body = json.load(e)
            failures += int(not assert_(e.code == 400 and expect in body.get("error", ""), f"{path} → 400 \"{body.get('error')}\""))
    return failures


def main():
    print(f"Testando contra {BASE}")
    total_failures = 0
    total_failures += test_eq_with_displayed_values()
    total_failures += test_inequalities()
    total_failures += test_date_range()
    total_failures += test_csv_export_with_filter()
    total_failures += test_error_cases()
    print(f"\n{'=' * 50}")
    if total_failures == 0:
        print("✓ TODOS OS TESTES PASSARAM")
        return 0
    print(f"✗ {total_failures} FALHA(S)")
    return 1


if __name__ == "__main__":
    sys.exit(main())

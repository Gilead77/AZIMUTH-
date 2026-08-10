# config/

The canonical default configuration lives at **`azimuth/config/default.yaml`**, not
here. `docs/04_SPEC_PYTHON_CLI.md` §3 places it inside the package, which is also the
only location that survives an install — `load_default()` resolves it through
`importlib.resources`.

`docs/00_README.md`'s repo-layout sketch shows `config/default.yaml` at the repo root
and the §4 command examples pass `--config config/default.yaml`. That discrepancy is
recorded as finding 17 in `docs/11_FINDINGS.md`; the package copy is treated as
canonical to avoid two files drifting apart.

This directory holds run-specific inputs that are *not* part of the package:

| File | Purpose |
|---|---|
| `grid.yaml` | Sweep grid for `azimuth sweep --grid config/grid.yaml` (M3, `docs/07_PARAMETERS.md` §2 staging) |

To start from the defaults:

```bash
python -c "import azimuth.config.schema as s; print(s.default_config_path())"
```

Any path works with `--config`; the packaged default is used when the flag is omitted.

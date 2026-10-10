"""GUI launcher and packaged-binary smoke test entry point."""
import json
import sys
from pathlib import Path


if __name__ == "__main__":
    if "--cleanup-uninstall" in sys.argv:
        from mixcut.lifecycle import cleanup_main
        sys.exit(cleanup_main())
    elif "--self-test" in sys.argv:
        from mixcut.selftest import self_test
        destination = Path(sys.argv[sys.argv.index("--self-test") + 1])
        try:
            report = self_test()
        except Exception as exc:
            destination.write_text(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), encoding="utf-8")
            raise
        destination.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    elif "--smoke-ui" in sys.argv:
        from mixcut.app import App
        app = App()
        app.update()
        app.destroy()
        Path(sys.argv[sys.argv.index("--smoke-ui") + 1]).write_text("ok", encoding="utf-8")
    else:
        from mixcut.app import main
        main()

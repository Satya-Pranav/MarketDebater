from app.data_aggregator import *  # noqa: F401,F403
from app.data_aggregator import _main as _legacy_main


if __name__ == "__main__":
	raise SystemExit(_legacy_main())

from bpc_opportunity_engine_v2 import main as run_engine
from export_bpc_v2_safe import main as export_safe
from build_bpc_v2_safe_mail_preview import main as build_preview


def main():
    run_engine()
    export_safe()
    build_preview()


if __name__ == '__main__':
    main()

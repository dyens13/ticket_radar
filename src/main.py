from __future__ import annotations

import argparse
import logging

from ticket_alarm import TicketAlarmService, load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Ticket radar telegram alarm")
    parser.add_argument("--config", default="config.yaml", help="YAML config path")
    parser.add_argument(
        "--mode",
        choices=["run", "new-alert-once", "preopen-alert-once"],
        default="run",
        help="run scheduler or execute one-shot jobs",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    config = load_config(args.config)
    service = TicketAlarmService(config)

    if args.mode == "new-alert-once":
        service.run_new_show_alert_check()
        return
    if args.mode == "preopen-alert-once":
        service.run_preopen_alert_check()
        return

    service.run()


if __name__ == "__main__":
    main()

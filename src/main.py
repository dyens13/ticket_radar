from __future__ import annotations

import argparse
import logging

from ticker_alarm import TicketAlarmService, load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Ticker radar telegram alarm")
    parser.add_argument("--config", default="config.yaml", help="YAML config path")
    parser.add_argument(
        "--mode",
        choices=["run", "daily-once", "reminder-once"],
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

    if args.mode == "daily-once":
        service.run_daily_registration_check()
        return
    if args.mode == "reminder-once":
        service.run_reminder_check()
        return

    service.run()


if __name__ == "__main__":
    main()

import argparse

from voice_turn_loop import (
    DEFAULT_ALSA_INPUT,
    DEFAULT_PULSE_SINK,
    loop_forever,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Always-on local voice assistant loop for Rock 3C")
    parser.add_argument("--seconds", type=int, default=4, help="Recording window per listen cycle")
    parser.add_argument("--input-device", default=DEFAULT_ALSA_INPUT)
    parser.add_argument("--sink", default=DEFAULT_PULSE_SINK)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--idle-sleep", type=float, default=0.4, help="Delay after an empty recognition cycle")
    parser.add_argument("--speak-cooldown", type=float, default=1.2, help="Delay after speaking to avoid immediate feedback")
    args = parser.parse_args()

    loop_forever(
        seconds=args.seconds,
        input_device=args.input_device,
        sink=args.sink,
        sample_rate=args.sample_rate,
        idle_sleep=args.idle_sleep,
        speak_cooldown=args.speak_cooldown,
    )


if __name__ == "__main__":
    main()

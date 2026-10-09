"""Run the Telegram bot using python -m social_video_downloader."""


if __name__ == "__main__":
    # Defer startup imports until the module is executed as a script.
    from social_video_downloader.bot import main

    main()

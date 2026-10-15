# Paper Scraper

Analyse a web page and write a Markdown paper with an AI provider.

## Development setup

The application package lives under `src/paper_scraper/`, tests are in
`tests/`, and generated papers and local credentials stay in the project root.
From the project folder, create an environment and install the project in
editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Run the tests with:

```bash
python -m unittest discover -s tests
```

## Web interface

After installing the project, run the local interface from the project folder:

```bash
python -m paper_scraper.web
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765). The app binds to
loopback by default. Set `PAPER_UI_PORT` to change the port. The interface
stores provider keys in the ignored `keys.json` file; it never displays saved
key values. You can also configure keys in that file or with the provider's
environment variable.

The web interface and CLI both save papers in `papers/` by default.
Click a paper in the library to read its rendered Markdown preview in the app.
The sidebar jumps between the analysis form and paper library.

For shared hosting, see the [cPanel deployment guide](CPANEL_DEPLOYMENT.md).
The app exposes a WSGI entry point for Passenger and supports HTTP Basic Auth
through `PAPER_UI_USER` and `PAPER_UI_PASSWORD` environment variables.

## Command line

```bash
paper-scraper https://example.com/article --provider anthropic
```

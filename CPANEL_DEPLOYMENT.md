# Deploy Paper Scraper on cPanel shared hosting

This deployment uses cPanel's Passenger WSGI support. It does not run the
development HTTP server. Your hosting provider must enable **Application
Manager** (or CloudLinux's **Setup Python App**), Python 3, pip, and Passenger.
Ask the host before proceeding if those features are missing. Shared-host
plans can limit outbound requests, memory, execution time, or background work;
confirm that the plan permits this workload and outbound HTTPS requests to your
chosen AI API and target websites.

## 1. Keep the app outside the public web root

Create a subdomain such as `papers.example.com` and deploy the app at the
subdomain root. Keep the source, `keys.json`, and generated papers in your home
directory, not in `public_html`. Use HTTPS for the subdomain before enabling
credentials. cPanel recommends an unused subdomain for web apps to avoid
conflicts with existing site files and rewrite rules.

In cPanel Terminal or SSH, clone the repository under your home directory:

```sh
cd ~
git clone YOUR_REPOSITORY_URL paper-scraper
cd ~/paper-scraper
```

Create a virtual environment using the Python version available on your host.
The cPanel Application Manager may provide a selected interpreter or create a
virtual environment for the app. Otherwise, use the host's documented Python
path:

```sh
python3 -m venv ~/virtualenv/paper-scraper
source ~/virtualenv/paper-scraper/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ~/paper-scraper
mkdir -p ~/paper-scraper/papers
```

If your host requires a versioned virtualenv directory, use its path in the
commands and set the `PAPER_PYTHON` environment variable below to that venv's
`bin/python` path. The `passenger_wsgi.py` file changes to the project folder,
then imports the app's WSGI entry point.

## 2. Register the app with cPanel

In **cPanel → Software → Application Manager**, choose **Register Application**
and set:

- **Application name:** `paper-scraper`
- **Deployment domain:** your new subdomain
- **Base application URL:** `/` (the subdomain root)
- **Application path:** `paper-scraper` (relative to your home directory)
- **Deployment environment:** `Production`

Deploy the application. If your host instead provides **Setup Python App**, set
the application root to `paper-scraper`, the application URL to the subdomain's
root, the startup file to `passenger_wsgi.py`, and the WSGI callable to
`application`. Use the same project virtualenv. The feature names and fields
vary by host and cPanel version.

## 3. Set the app credentials

In the app's environment variables, set:

```text
PAPER_UI_USER=your-private-username
PAPER_UI_PASSWORD=a-long-unique-password
```

If you created a separate virtualenv, also set `PAPER_PYTHON` to its full
interpreter path, for example `/home/CPANEL_USER/virtualenv/paper-scraper/bin/python`.
Do not include a colon in the username. Use a unique password and keep the app
behind HTTPS. These credentials protect the interface and the API routes,
including the endpoint that writes provider keys.

Open the subdomain. The browser will request the Basic Auth credentials. In the
UI's **Settings**, add the AI provider key; it is written to `keys.json` in the
project directory. Alternatively create that JSON file yourself:

```json
{
  "anthropic": "YOUR_API_KEY"
}
```

Restrict that file to your cPanel account (`chmod 600 ~/paper-scraper/keys.json`)
and keep it out of version control. Never paste real API keys into a public
repository or a support ticket.

## 4. Restart and check logs

After changing code or dependencies, restart the Passenger app using cPanel's
restart control. If unavailable, create the restart marker in the app root:

```sh
mkdir -p ~/paper-scraper/tmp
touch ~/paper-scraper/tmp/restart.txt
```

Check the app's `stderr.log` in the project folder if it does not start. Verify
that the app can write to `papers/`, and that the host allows outgoing HTTPS
connections. Papers are saved under `~/paper-scraper/papers/`.

## Notes for shared hosting

- The cPanel app manager must support Python WSGI/Passenger. A static-only
  hosting plan cannot run this application.
- Keep this private research UI behind its login; it is intended for the owner
  of the cPanel account, not for anonymous public use.
- Providers may impose request, context, and token quotas. Long summarization
  calls may exceed a shared host's process or proxy timeout.
- Keep a backup of the repository's `papers/` output and the private key file.

## cPanel references

- [How to Install a Python WSGI Application](https://docs.cpanel.net/knowledge-base/web-services/how-to-install-a-python-wsgi-application/)
- [Application Manager](https://docs.cpanel.net/cpanel/software/application-manager/)
- [Using Passenger Applications](https://docs.cpanel.net/knowledge-base/web-services/using-passenger-applications/)
- [How Domains Serve Content](https://docs.cpanel.net/knowledge-base/cpanel-product/how-domains-serve-content/)

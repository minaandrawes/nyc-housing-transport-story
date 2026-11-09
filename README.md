# NYC Permits and Street Safety

Data Engineering and Visualization, Project Milestone 1 (GIU)

**Live website:** https://nyc-housing-transport-story.onrender.com/
(Free hosting: if nobody has opened it for a while, the first load can take about 50 seconds.)

## What this project does
It links two NYC Open Data datasets that share no common key, by ZIP code and month:
- **Housing:** DOB NOW: Build - Approved Permits (https://data.cityofnewyork.us/d/rbx6-tga4)
- **Transportation:** Motor Vehicle Collisions - Crashes (https://data.cityofnewyork.us/d/h9gi-nx95)

Both are cleaned and aggregated to ZIP code x month (2023-2025), then explored in a Dash website with 10 research questions and 10 interactive charts, including charts that combine both domains.

## Repository contents
- `app.py`: the Dash website (layout, filters, Generate Report button, story section)
- `charts.py`: the 10 chart functions
- `search.py`: search mode (turns text such as "Brooklyn 2024 scaffolds injury" into filters)
- `data/integrated_clean.csv`: the final integrated dataset used by the website
- `assets/style.css`: website styling
- `notebook/`: the notebook with dataset overview, EDA, cleaning, integration, research questions, prompts used and dataset links
- `requirements.txt`: Python packages

## Setup steps (run locally)
1. Install Python 3.10 or newer and Git.
2. Clone the repository:
   ```
   git clone https://github.com/minaandrawes/nyc-housing-transport-story.git
   cd nyc-housing-transport-story
   ```
3. (Optional) create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
4. Install the packages:
   ```
   pip install -r requirements.txt
   ```
5. Start the website:
   ```
   python app.py
   ```
6. Open http://127.0.0.1:8050 in a browser.

## How to use the website
- Pick filters: Borough, Year, Permit type, Crash type, ZIP code. Or type a search such as `Brooklyn 2024 scaffolds injury` to fill the filters automatically.
- Click **Generate Report** to update all 10 charts and the summary boxes.
- The story section at the top gives the question, key findings, limitations and the benefit to NYC.

## Deployment steps (Render, free plan)
1. Push the repository to GitHub.
2. On render.com, sign in with GitHub and choose **New**, then **Web Service**.
3. Select this repository (branch `main`).
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn app:server`
6. Choose the **Free** instance and click **Deploy web service**.
7. When the status says **Live**, open the `.onrender.com` link.

## Team contributions
- **Mina Ayman Andrawes (16003514):** all work in this milestone: dataset selection and loading, exploration, cleaning, integration, the 10 research questions and charts, the Dash website, GitHub repository, deployment and this README.
- The other four team members could not be reached during this milestone and did not contribute.
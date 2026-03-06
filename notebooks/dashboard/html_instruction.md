# Interactive HTML Export Instructions

This document explains how to convert the Panel dashboard (`app.py`) into a standalone interactive HTML file that runs in the browser without any server.

## Overview

We will use **PyCafe** to export the Panel application as a single self-contained HTML file. PyCafe uses Pyodide (Python in WebAssembly) to run Python directly in the browser, enabling full interactivity (dropdowns, plots, ANOVA updates) without a backend server.

## Method 1: PyCafe GUI (Recommended for Small Projects)

### Step 1: Prepare Your Files

Ensure you have the following files ready in the `notebooks/dashboard/` directory:

```
notebooks/dashboard/
├── app.py              # The Panel dashboard code
└── requirements.txt    # Python dependencies
```

### Step 2: Create a Zip Archive

1. Navigate to the `notebooks/dashboard/` directory
2. Select both `app.py` and `requirements.txt`
3. Create a zip file named `dashboard.zip`

### Step 3: Upload to PyCafe

1. Open your browser and go to **https://py.cafe**
2. If prompted, sign in or create a free account
3. On the homepage, look for **"Panel"** framework option (or click "New" → "Panel")
4. Look for an **"Upload"** or **"Import"** option
5. Upload your `app.py` and `requirements.txt` files

   Alternatively, you can paste the contents of `app.py` into the editor on PyCafe and create a `requirements.txt` file there.

### Step 4: Configure Requirements

If you created files on PyCafe, ensure `requirements.txt` contains:

```
panel
pandas
numpy
matplotlib
seaborn
scipy
```

### Step 5: Test the App

1. Click **"Run"** or **"Preview"** to verify the app works in PyCafe
2. Test the dropdowns and verify plots render correctly

### Step 6: Export as HTML

1. Click the **"Share"** button (usually in the top-right corner)
2. Select the **"Export"** tab
3. Click **"Download as HTML"**
4. PyCafe will generate and download a file like `app.html`

### Step 7: Test the HTML File

1. Open the downloaded HTML file in a modern browser (Chrome, Firefox, Edge)
2. Wait a moment for PyCafe to initialize (it will show a loading indicator)
3. Test all interactive features:
   - Dropdown selectors for variable selection
   - Scatter plots updating with correlations
   - ANOVA violin plots

### Important Notes for GUI Method

- **File size limit**: 10 MB on the free PyCafe tier
- If your app exceeds this limit, use the CLI method below
- The HTML file includes the Python runtime, so it's larger than typical HTML

---

## Method 2: Command Line (Recommended for Large Projects)

The CLI method supports larger projects (up to 400 MB) and doesn't require manual file upload.

### Prerequisites

Install the `pycafe-server` tool:

```bash
# Using pip
pip install pycafe-server

# Or using uvx (no installation required)
uvx pycafe-server --help
```

### Step 1: Prepare Your Project Directory

Ensure your project directory contains:

```
your-project/
├── app.py
└── requirements.txt
```

### Step 2: Export Using CLI

#### Option A: Using Self-Hosted PyCafe Server

If you have your own PyCafe server:

```bash
# Set environment variables
export PYCAFE_API_KEY=your_api_key_here
export PYCAFE_CLIENT_URL=https://your-pycafe-domain.com

# Run export
pycafe-server export-html \
  --name your-app-name \
  --input-dir path/to/your-project \
  --pyodide 0.27.2 \
  --type panel
```

#### Option B: Using Public PyCafe (No Server Required)

```bash
# Export using public PyCafe
uvx pycafe-server export-html \
  --public \
  --name eda-correlation-dashboard \
  --input-dir notebooks/dashboard \
  --pyodide 0.27.2 \
  --type panel
```

### Step 3: Locate the Output

The command will generate a file named `eda-correlation-dashboard.html` in the current directory.

---

## Verifying the HTML File

### What to Expect

1. **Initial Load**: The browser will show a loading spinner while PyCafe initializes the Python runtime (may take 10-30 seconds on first load)

2. **Functionality**: All Panel widgets should work:
   - `Select` dropdowns for variable selection
   - Matplotlib plots with correlation values
   - Interactive violin plots with ANOVA results

3. **File Size**: The HTML file will be 15-50 MB depending on dependencies

### Browser Compatibility

Works in:

- Google Chrome (recommended)
- Mozilla Firefox
- Microsoft Edge

May not work in:

- Safari (some WebAssembly restrictions)
- Mobile browsers (performance may vary)

---

## Troubleshooting

### Issue: Dropdowns don't respond

**Cause**: The Python runtime may not have fully loaded.

**Solution**: Wait for the "PyCafe" loading indicator to disappear, then refresh the page.

### Issue: Plots don't render

**Cause**: Matplotlib backend issue in WebAssembly.

**Solution**: Ensure you're using `pn.pane.Matplotlib()` with figure objects (not functions). The app.py has been configured for this.

### Issue: "Module not found" errors

**Cause**: Missing dependencies.

**Solution**: Verify `requirements.txt` includes all needed packages and matches what's in `app.py`:

- panel
- pandas
- numpy
- matplotlib
- seaborn
- scipy

### Issue: Application is slow

**Cause**: First load downloads Python runtime (~15 MB).

**Solution**: Subsequent loads are faster due to browser caching. Consider using Chrome for best performance.

---

## Alternative Approaches

If PyCafe doesn't meet your needs, consider these alternatives:

### 1. Voila (Requires Hosting)

Deploy to a server instead of single HTML:

```bash
voila notebooks/dashboard/app.py
```

### 2. Streamlit + stlite

Convert to Streamlit and use stlite for browser-based execution (requires code changes).

### 3. Jupyter Book

Create a static documentation site (loses interactivity):

```bash
jupyter-book build .
```

---

## Summary

| Method     | Max Size  | Setup Complexity | Best For                  |
| ---------- | --------- | ---------------- | ------------------------- |
| PyCafe GUI | 10 MB     | Easy             | Quick sharing, small apps |
| PyCafe CLI | 400 MB    | Moderate         | Larger apps, automation   |
| Voila      | Unlimited | Moderate         | Server-based deployment   |

For this dashboard, **Method 1 (PyCafe GUI)** is recommended as it's the simplest and the dashboard is well under the 10 MB limit.

from flask import Flask, render_template, request, send_file, session, redirect, url_for, jsonify
from flask_session import Session
import pandas as pd
import io, csv, base64, zipfile, socket, webbrowser
from datetime import datetime
import numpy as np
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from threading import Timer
from waitress import serve

# Define the columns that are required in the uploaded CSV files.
REQUIRED_COLUMNS = ['Altitude', 'Temperature', 'Pressure', 'Humidity', 'Heading', 'Speed']

# Initialize the Flask application.
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Configure server-side session handling to store data in the filesystem.
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './.flask_session/'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_FILE_THRESHOLD'] = 500
Session(app)

# Persistent upload folder
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploaded_files")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Application metadata.
APP_VERSION = "v2.2"  # Updated version
DEVELOPER = {
    "team": "MET Grp-3",
    "organization": "DRDO"
}

def safe_read_csv(file_stream):
    content = file_stream.read()
    try:
        dialect = csv.Sniffer().sniff(content.decode('utf-8'), delimiters=',;')
        file_stream.seek(0)
        return pd.read_csv(io.StringIO(content.decode('utf-8')), delimiter=dialect.delimiter)
    except Exception:
        file_stream.seek(0)
        return pd.read_csv(file_stream)

def create_analysis_pdf(df):
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # Temperature vs Altitude
        fig1, ax1 = plt.subplots(figsize=(8, 6))
        ax1.plot(df['Altitude'], df['Temperature'], color='red')
        ax1.set_title("Temperature vs Altitude")
        ax1.set_xlabel("Altitude (m)")
        ax1.set_ylabel("Temperature (K)")
        ax1.grid(True)
        pdf.savefig(fig1)
        plt.close(fig1)

        # Pressure vs Altitude
        fig2, ax2 = plt.subplots(figsize=(8, 6))
        ax2.plot(df['Altitude'], df['Pressure'], color='blue')
        ax2.set_title("Pressure vs Altitude")
        ax2.set_xlabel("Altitude (m)")
        ax2.set_ylabel("Pressure (hPa)")
        ax2.grid(True)
        pdf.savefig(fig2)
        plt.close(fig2)

        # Humidity vs Altitude
        fig3, ax3 = plt.subplots(figsize=(8, 6))
        ax3.plot(df['Altitude'], df['Humidity'], color='green')
        ax3.set_title("Humidity vs Altitude")
        ax3.set_xlabel("Altitude (m)")
        ax3.set_ylabel("Humidity (%)")
        ax3.grid(True)
        pdf.savefig(fig3)
        plt.close(fig3)

        # Wind Speed vs Altitude
        fig4, ax4 = plt.subplots(figsize=(8, 6))
        ax4.plot(df['Altitude'], df['Speed'], color='purple')
        ax4.set_title("Wind Speed vs Altitude")
        ax4.set_xlabel("Altitude (m)")
        ax4.set_ylabel("Wind Speed (knots)")
        ax4.grid(True)
        pdf.savefig(fig4)
        plt.close(fig4)

        # Wind Direction vs Altitude
        fig5, ax5 = plt.subplots(figsize=(8, 6))
        ax5.plot(df['Altitude'], df['Heading'], color='orange')
        ax5.set_title("Wind Direction vs Altitude")
        ax5.set_xlabel("Altitude (m)")
        ax5.set_ylabel("Wind Direction (°)")
        ax5.grid(True)
        pdf.savefig(fig5)
        plt.close(fig5)

        # Wind Rose
        try:
            wind_df = df[['Heading', 'Speed']].dropna()
            fig6 = plt.figure(figsize=(8, 8))
            ax6 = fig6.add_subplot(111, polar=True)
            wind_df['DirBin'] = pd.cut(wind_df['Heading'], bins=np.arange(0, 361, 30),
                                       labels=np.arange(15, 360, 30), include_lowest=True)
            rose_data = wind_df.groupby('DirBin').size()
            if not rose_data.empty:
                theta = np.radians(rose_data.index.astype(float))
                radii = rose_data.values
                colors = plt.cm.viridis(radii / max(radii))
                ax6.bar(theta, radii, width=np.radians(30), color=colors, edgecolor='black')
                ax6.set_theta_zero_location('N')
                ax6.set_theta_direction(-1)
                ax6.set_title("Wind Rose", va='bottom', y=1.1)
                pdf.savefig(fig6)
            plt.close(fig6)
        except Exception as e:
            print(f"Error adding wind rose to PDF: {e}")

    buf.seek(0)
    return buf

def create_wind_rose(df):
    try:
        df = df[['WindDirection_deg', 'WindSpeed_knots']].copy()
        df.rename(columns={'WindDirection_deg': 'Heading', 'WindSpeed_knots': 'Speed'}, inplace=True)
        df['Heading'] = pd.to_numeric(df['Heading'], errors='coerce')
        df['Speed'] = pd.to_numeric(df['Speed'], errors='coerce')
        df = df.dropna()

        if df.empty:
            print("Wind Rose: No valid data after cleaning.")
            return None

        fig = plt.figure(figsize=(6, 6), facecolor='none')
        ax = fig.add_subplot(111, polar=True, facecolor='none')
        df['DirBin'] = pd.cut(df['Heading'], bins=np.arange(0, 361, 30),
                              labels=np.arange(15, 360, 30), include_lowest=True)
        rose_data = df.groupby('DirBin').size()

        if rose_data.empty:
            print("Wind Rose: No grouped data available.")
            return None

        theta = np.radians(rose_data.index.astype(float))
        radii = rose_data.values
        colors = plt.cm.viridis(radii / max(radii))
        ax.bar(theta, radii, width=np.radians(30), color=colors, edgecolor='black')
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.set_title("Wind Rose (Frequency by Direction)", va='bottom', y=1.1)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', transparent=True)
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return image_base64
    except Exception as e:
        print(f"Wind Rose generation failed: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    result = []
    error = None
    filenames = session.get("filenames", [])
    df_map = {}
    metadata_map = {}
    wind_rose_image = session.get("wind_rose_image")

    # Load existing data from session
    if 'csv_data' in session:
        for fname, csv_str in session['csv_data'].items():
            try:
                df = pd.read_csv(io.StringIO(csv_str))
                df = df[REQUIRED_COLUMNS].apply(pd.to_numeric, errors='coerce')
                if df.dropna(how='all').empty:
                    continue
                df_map[fname] = df
            except Exception:
                continue

    if request.method == 'POST':
        remove_filename = request.form.get("remove_file")
        if remove_filename:
            filenames = [f for f in filenames if f != remove_filename]
            session.get('csv_data', {}).pop(remove_filename, None)
            session['filenames'] = filenames
            return redirect(url_for("index"))

        uploaded_files = request.files.getlist('files')
        if uploaded_files and any(file.filename for file in uploaded_files):
            if 'csv_data' not in session:
                session['csv_data'] = {}
            if 'uploaded_files' not in session:
                session['uploaded_files'] = []

            for file in uploaded_files:
                if file.filename:
                    try:
                        df = safe_read_csv(file)

                        # 🔹 Added: Normalize column names
                        column_mapping = {
                            'Altitude(m)': 'Altitude',
                            'Altitude (m)': 'Altitude',
                            'Temperature(K)': 'Temperature',
                            'Temperature (K)': 'Temperature',
                            'Pressure(hPa)': 'Pressure',
                            'Pressure (hPa)': 'Pressure',
                            'Humidity(%)': 'Humidity',
                            'Humidity (%)': 'Humidity',
                            'Wind_Direction': 'Heading',
                            'Wind Direction': 'Heading',
                            'Wind_Direction(deg)': 'Heading',
                            'Wind Direction (deg)': 'Heading',
                            'WindSpeed': 'Speed',
                            'Wind_Speed': 'Speed',
                            'Wind Speed': 'Speed',
                            'WindSpeed(knots)': 'Speed',
                            'Wind Speed (knots)': 'Speed'
                        }
                        df.rename(columns=column_mapping, inplace=True)

                        missing = set(REQUIRED_COLUMNS) - set(df.columns)
                        if missing:
                            error = f"File '{file.filename}' missing columns: {', '.join(missing)}"
                            continue

                        df = df[REQUIRED_COLUMNS].apply(pd.to_numeric, errors='coerce')
                        if df.dropna(how='all').empty:
                            error = f"File '{file.filename}' has no usable numeric data."
                            continue

                        save_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                        file.seek(0)
                        file.save(save_path)
                        if save_path not in session['uploaded_files']:
                            session['uploaded_files'].append(save_path)

                        session['csv_data'][file.filename] = df.to_csv(index=False)
                        df_map[file.filename] = df
                        if file.filename not in filenames:
                            filenames.append(file.filename)
                    except Exception as e:
                        error = f"Error reading file '{file.filename}': {str(e)}"

            session['filenames'] = filenames
            session['last_updated'] = datetime.now().strftime('%d %B %Y, %I:%M %p')

    # Fallback: reload from disk if memory is empty
    if not df_map and 'uploaded_files' in session:
        for path in session['uploaded_files']:
            if os.path.exists(path):
                try:
                    df = pd.read_csv(path)
                    df = df[REQUIRED_COLUMNS].apply(pd.to_numeric, errors='coerce')
                    if df.dropna(how='all').empty:
                        continue
                    fname = os.path.basename(path)
                    df_map[fname] = df
                except Exception:
                    continue

    for fname, df in df_map.items():
        metadata_map[fname] = {
            "rows": df.shape[0],
            "columns": list(df.columns)
        }

    step_input = request.form.get('altitude', '')
    if request.method == 'POST' and step_input:
        if not df_map:
            error = "Please upload at least one valid CSV file before processing."
        else:
            try:
                step = float(step_input.strip())
                if step <= 0:
                    raise ValueError("Step must be a positive number.")

                results = []
                for fname, df in df_map.items():
                    altitudes = df['Altitude'].dropna().unique()
                    if altitudes.size == 0:
                        continue
                    max_alt = altitudes.max()
                    step_points = np.arange(0, max_alt + step, step)

                    for alt in step_points:
                        idx = (df['Altitude'] - alt).abs().idxmin()
                        closest_row = df.loc[idx]
                        matched_altitude = closest_row['Altitude']
                        altitude_diff = abs(matched_altitude - alt)
                        
                        row = {
                            'Dataset': fname,
                            'Input_Altitude': alt,
                            'Matched_Altitude_m': matched_altitude,
                            'Altitude_Diff_m': altitude_diff,
                            'Temperature_K': closest_row.get('Temperature', 'N/A'),
                            'Pressure_hPa': closest_row.get('Pressure', 'N/A'),
                            'Humidity_percent': closest_row.get('Humidity', 'N/A'),
                            'WindSpeed_knots': closest_row.get('Speed', 'N/A'),
                            'WindDirection_deg': closest_row.get('Heading', 'N/A')
                        }
                        results.append(row)

                result = results
                df_result = pd.DataFrame(result)
                session['result'] = df_result.to_csv(index=False)
                wind_rose_image = create_wind_rose(df_result)
                session['wind_rose_image'] = wind_rose_image
            except Exception as e:
                error = f"Error processing input: {str(e)}"

    return render_template('index.html',
                           result=result,
                           error=error,
                           filenames=filenames,
                           metadata_map=metadata_map,
                           last_updated=session.get("last_updated"),
                           app_version=APP_VERSION,
                           developer=DEVELOPER,
                           wind_rose_image=wind_rose_image)

@app.route('/download/csv')
def download_csv():
    if 'result' not in session:
        return "No processed data available to download.", 400
    csv_data = session['result']
    return send_file(
        io.BytesIO(csv_data.encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='processed_data.csv'
    )

@app.route('/download/zip')
def download_zip():
    if 'result' not in session and 'csv_data' not in session:
        return "No data available to download.", 400

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if 'result' in session:
            csv_data = session['result']
            zipf.writestr("processed_data.csv", csv_data)

        if 'csv_data' in session:
            all_csv_data = session.get('csv_data', {})
            for filename, csv_str in all_csv_data.items():
                try:
                    df = pd.read_csv(io.StringIO(csv_str))
                    if not set(REQUIRED_COLUMNS).issubset(df.columns):
                        print(f"Skipping PDF creation for {filename} due to missing columns.")
                        continue
                    pdf_buffer = create_analysis_pdf(df)
                    pdf_filename = f"analysis_plots_{filename.rsplit('.', 1)[0]}.pdf"
                    zipf.writestr(pdf_filename, pdf_buffer.read())
                except Exception as e:
                    print(f"Failed to create PDF for {filename}: {e}")

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='processed_output.zip'
    )

@app.route('/clear_session')
def clear_session():
    session.clear()
    return redirect(url_for('index'))

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def open_browser(port):
    webbrowser.open_new(f"http://127.0.0.1:{port}")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0"
    from waitress import serve
    serve(app, host=host, port=port)


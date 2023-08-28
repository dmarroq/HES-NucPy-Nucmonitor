import streamlit as st
import requests
import pandas as pd
import json
import io
import datetime

st.title("Nucmonitor App")

# Get user input (e.g., dates)
start_date = st.date_input("Start Date")
end_date = st.date_input("End Date")
photo_date = st.checkbox("Photodate")

if photo_date == True:
    past_date = st.date_input("Cutoff Date")
else:
    past_date = None


# When the user clicks a button, send the input to the Flask server
if st.button("Get RTE Data"):
    response_rte = requests.get(f"http://127.0.0.1:5000/nucpy/v1/rte?start_date={start_date}&end_date={end_date}")
    if response_rte.status_code == 200:
        rte_data = response_rte.json()  # Use .json() method to parse JSON content
        st.write("Data received from Flask:")
        st.write(rte_data)
    else:
        st.write("Failed to retrieve data from Flask API")


if st.button("Get Nucmonitor"):

    response_nucmonitor = requests.get(f"http://127.0.0.1:5000/nucpy/v1/nucmonitor?start_date={start_date}&end_date={end_date}&photo_date={photo_date}&past_date={past_date}")
   
    if response_nucmonitor.status_code == 200:
        st.sidebar.write("FILTERS")
        nucmonitor_data = response_nucmonitor.json()  # Use .json() method to parse JSON content
        nucmonitor_json = json.loads(nucmonitor_data)  # Parse JSON content
        st.write(nucmonitor_json)
        # Convert JSON data to a DataFrame
        df = pd.DataFrame(nucmonitor_json)  # Assuming nucmonitor_data is a list of dictionaries

        st.write("Data received from Flask:")
        # Remove the index column and set the Date column as the index
        # df.set_index("Date", inplace=True)

        st.write(df)  # Display DataFrame

        st.title("Power Plant Data Visualization")
        df1 = df.iloc[:-1, :-1]
        # Create a line chart using Streamlit
        st.line_chart(df1)

        # Add a download button
        if df is not None and not df.empty:
            current_datetime = datetime.datetime.now()
            current_year = current_datetime.strftime('%Y')
            current_month = current_datetime.strftime('%m')
            current_day = current_datetime.strftime('%d')
            current_hour = current_datetime.strftime('%H')
            current_minute = current_datetime.strftime('%M')
            current_second = current_datetime.strftime('%S')
            # Create a BytesIO object to hold the Excel data
            excel_buffer = io.BytesIO()

            # Save the DataFrame to the BytesIO object as an Excel file
            df.to_excel(excel_buffer, index=True)

            # Set the cursor position to the beginning of the BytesIO object
            excel_buffer.seek(0)

            # Provide the BytesIO object to the download button
            download_button = st.download_button(
                label="Download Excel",
                data=excel_buffer,
                file_name=f"nucmonitor_data_{current_year}-{current_month}-{current_day}-h{current_hour}m{current_minute}s{current_second}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    else:
        st.write("Failed to retrieve data from Flask API")
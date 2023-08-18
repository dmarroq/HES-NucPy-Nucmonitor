import streamlit as st
import requests
import pandas as pd
import json

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
    # response_rte = requests.get(f"http://127.0.0.1:5000/nucpy/v1/rte?start_date={start_date}&end_date={end_date}")
    # if response_rte.status_code == 200:
    #     rte_data = response_rte.json()
    #     rte_data_json = json.dumps(rte_data)
    # response_mongo = requests.get(f"http://127.0.0.1:5000/nucpy/v1/raw")
    # if response_mongo.status_code == 200:
    #     mongo_data = response_mongo.json()
    # response_nucmonitor = requests.get(f"http://127.0.0.1:5000/nucpy/v1/nucmonitor?rte_data={rte_data_json}&start_date={start_date}&end_date={end_date}&photo_date={photo_date}&past_date={past_date}")
    response_nucmonitor = requests.get(f"http://127.0.0.1:5000/nucpy/v1/nucmonitor?start_date={start_date}&end_date={end_date}&photo_date={photo_date}&past_date={past_date}")
   
    if response_nucmonitor.status_code == 200:
        nucmonitor_data = response_nucmonitor.json()  # Use .json() method to parse JSON content
        nucmonitor_json = json.loads(nucmonitor_data)  # Parse JSON content
        # nucmonitor_data_list = [{'key': key, 'value': value} for key, value in nucmonitor_data.items()]
        st.write(nucmonitor_json)
        # Convert JSON data to a DataFrame
        df = pd.DataFrame(nucmonitor_json)  # Assuming nucmonitor_data is a list of dictionaries
        # df = pd.read_json(nucmonitor_json)
        # df = pd.DataFrame.from_dict(nucmonitor_data, orient='index')
        # df = df.copy().transpose()
        # Convert nested dictionaries to JSON strings
        # nucmonitor_data = {key: json.dumps(value) for key, value in nucmonitor_data.items()}
        
        # Convert JSON data to a DataFrame
        # df = pd.DataFrame(nucmonitor_data.items(), columns=['Location', 'Data'])

        st.write("Data received from Flask:")
        st.write(df)  # Display DataFrame
    else:
        st.write("Failed to retrieve data from Flask API")
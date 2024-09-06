import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
import plotly.express as px
from geopy.geocoders import Nominatim
from fuzzywuzzy import process

@st.cache_data
def load_data():
    data = pd.read_excel('News GIS.xlsx', engine='openpyxl')
    data['Date'] = pd.to_datetime(data['Date'])
    return data

@st.cache_data
def load_world():
    url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
    return gpd.read_file(url)

@st.cache_data
def load_world_cities():
    return pd.read_csv('worldcities.csv')

@st.cache_data
def fuzzy_match_city(city_name, limit=5, threshold=70):
    cities = load_world_cities()['city'].unique()
    matches = process.extract(city_name, cities, limit=limit)
    return [match for match, score in matches if score >= threshold]

@st.cache_data
def geocode(city, country):
    geolocator = Nominatim(user_agent="my_app")
    try:
        location = geolocator.geocode(f"{city}, {country}")
        if location:
            return (location.latitude, location.longitude)
    except:
        pass
    return None

@st.cache_data
def preprocess_data(data):
    def geocode_and_correct(row):
        coords = geocode(row['City'], row['Country'])
        if coords is None:
            matches = fuzzy_match_city(row['City'])
            if matches:
                for match in matches:
                    coords = geocode(match, row['Country'])
                    if coords:
                        row['City'] = match
                        break
        return pd.Series({'Coordinates': coords, 'City': row['City']})

    result = data.apply(geocode_and_correct, axis=1)
    data['Coordinates'] = result['Coordinates']
    data['City'] = result['City']
    return data.dropna(subset=['Coordinates'])

@st.cache_data
def filter_data(data, type_filter, category_filter, country_filter, impact_filter, severity_filter, start_date, end_date, search_term):
    filtered_data = data
    if type_filter:
        filtered_data = filtered_data[filtered_data['Type'].isin(type_filter)]
    if category_filter:
        filtered_data = filtered_data[filtered_data['Category'].isin(category_filter)]
    if country_filter:
        filtered_data = filtered_data[filtered_data['Country'].isin(country_filter)]
    if impact_filter:
        filtered_data = filtered_data[filtered_data['Impact'].isin(impact_filter)]
    if severity_filter:
        filtered_data = filtered_data[filtered_data['Severity'].isin(severity_filter)]
    
    filtered_data = filtered_data[(filtered_data['Date'] >= start_date) & (filtered_data['Date'] <= end_date)]

    if search_term:
        filtered_data = filtered_data[filtered_data['Title'].str.contains(search_term, case=False) |
                                      filtered_data['Country'].str.contains(search_term, case=False) |
                                      filtered_data['City'].str.contains(search_term, case=False)]
    
    return filtered_data

def get_marker_color(category):
    colors = {
        'Explosive': 'gray',
        'Biological': 'green',
        'Radiological': 'red',
        'Chemical': 'orange',
        'Nuclear': 'blue'
    }
    return colors.get(category, 'gray')

def create_popup_content(row):
    return f"""
    <b>{row['Title']}</b><br>
    Category: {row['Category']}<br>
    Date: {row['Date']}<br>
    Location: {row['City']}, {row['Country']}<br>
    Casualty: {row['Casualty']}<br>
    Injury: {row['Injury']}<br>
    Impact: {row['Impact']}<br>
    Severity: {row['Severity']}<br>
    <a href="{row['Link']}" target="_blank">Read More</a>
    """

@st.cache_data
def create_plotly_map(filtered_data):
    traces = []
    for category in filtered_data['Category'].unique():
        df_category = filtered_data[filtered_data['Category'] == category]
        trace = go.Scattermapbox(
            lat=df_category['Coordinates'].apply(lambda x: x[0] if x else None),
            lon=df_category['Coordinates'].apply(lambda x: x[1] if x else None),
            mode='markers',
            marker=go.scattermapbox.Marker(
                size=10,
                color=get_marker_color(category),
                opacity=0.7
            ),
            text=df_category.apply(lambda row: create_popup_content(row), axis=1),
            hoverinfo='text',
            name=category,
            showlegend=True
        )
        traces.append(trace)

    fig = go.Figure(traces)

    fig.update_layout(
        mapbox_style="carto-darkmatter",
        mapbox=dict(
            center=dict(lat=20, lon=0),
            zoom=1.5
        ),
        showlegend=True,
        legend_title_text='Category',
        margin={"r":0,"t":0,"l":0,"b":0},
        height=600
    )

    return fig

@st.cache_data
def create_plotly_heatmap(heat_data):
    fig = go.Figure(go.Densitymapbox(
        lat=heat_data['lat'],
        lon=heat_data['lon'],
        z=heat_data['LinkCount'],
        radius=30,
        colorscale='Viridis',
        zmin=0,
        zmax=heat_data['LinkCount'].max(),
        showscale=True
    ))

    fig.update_layout(
        mapbox_style="carto-darkmatter",
        mapbox=dict(
            center=dict(lat=20, lon=0),
            zoom=1.5
        ),
        margin={"r":0,"t":0,"l":0,"b":0},
        height=600
    )

    return fig

def main():
    st.set_page_config(layout="wide")
    st.title("CBRNE Incident Map")

    data = load_data()
    world = load_world()
    

    data = preprocess_data(data)
    
    search_term = st.text_input("Search incidents", "")
    
    st.sidebar.header("Filters")
    type_filter = st.sidebar.multiselect("Type", data['Type'].unique())
    category_filter = st.sidebar.multiselect("Category", data['Category'].unique())
    country_filter = st.sidebar.multiselect("Country", data['Country'].unique())
    impact_filter = st.sidebar.multiselect("Impact", data['Impact'].unique())
    severity_filter = st.sidebar.multiselect("Severity", data['Severity'].unique())
    
    min_date = data['Date'].min().date()
    max_date = data['Date'].max().date()
    date_range = st.sidebar.date_input("Date Range", [min_date, max_date])
    
    start_date = pd.to_datetime(date_range[0])
    end_date = pd.to_datetime(date_range[1])


    filtered_data = filter_data(data, type_filter, category_filter, country_filter, impact_filter, severity_filter, start_date, end_date, search_term)

    tab1, tab2, tab3 = st.tabs(["Incident Map", "Heatmap", "Data"])

    with tab1:
        st.subheader("Incident Map")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig = create_plotly_map(filtered_data)
            st.plotly_chart(fig, use_container_width=True)

        with col2:

            category_counts = filtered_data['Category'].value_counts()
            fig1 = px.pie(values=category_counts.values, names=category_counts.index, title="Distribution by Category")
            fig1.update_layout(template="plotly_dark", height=300)
            st.plotly_chart(fig1, use_container_width=True)

            country_counts = filtered_data['Country'].value_counts().reset_index()
            country_counts.columns = ['Country', 'Count']
            fig2 = px.bar(country_counts, x='Country', y='Count', title="Distribution by Country")
            fig2.update_layout(
                template="plotly_dark", 
                height=400, 
                xaxis_title="Countries", 
                yaxis_title="Count",
                showlegend=False,
                xaxis_ticktext=[''],
                xaxis_tickvals=[],
                hovermode="closest"
            )
            fig2.update_traces(
                hovertemplate="<b>%{x}</b><br>Count: %{y}"
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Trend of Articles Over Time")
        articles_by_date = filtered_data.groupby('Date').size().reset_index(name='count')
        fig3 = px.line(articles_by_date, x='Date', y='count')
        fig3.update_layout(
            template="plotly_dark", 
            height=300, 
            xaxis_title="Date", 
            yaxis_title="Number of Articles",
            showlegend=False
        )
        st.plotly_chart(fig3, use_container_width=True)

    with tab2:
        st.subheader("Incident Heatmap")
        heat_data = filtered_data.copy()
        heat_data['lat'] = heat_data['Coordinates'].apply(lambda x: x[0])
        heat_data['lon'] = heat_data['Coordinates'].apply(lambda x: x[1])
        heat_data['LinkCount'] = 1
        fig = create_plotly_heatmap(heat_data)
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("Filtered Data")
        display_columns = ['Title', 'Country', 'City', 'Date', 'Casualty', 'Injury', 'Impact', 'Severity']
        df_display = filtered_data[display_columns].copy()
        df_display['Link'] = filtered_data['Link'].apply(lambda x: f'<a href="{x}" target="_blank">Link</a>')
        st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim

# Load data
@st.cache_data
def load_data():
    data = pd.read_excel('News GIS.xlsx', engine='openpyxl')
    return data

# Load world boundaries
@st.cache_data
def load_world():
    url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
    return gpd.read_file(url)

# Geocode function
@st.cache_data
def geocode(location):
    geolocator = Nominatim(user_agent="my_app")
    try:
        loc = geolocator.geocode(location)
        if loc:
            return (loc.latitude, loc.longitude)
    except:
        pass
    return None

# Define marker icons for each category
def get_marker_icon(category):
    icons = {
        'Explosive': 'bomb',
        'Biological': 'bug',
        'Radiological': 'radiation',
        'Chemical': 'flask',
        'Nuclear': 'atom'
    }
    return icons.get(category, 'info-sign')

# Create a formatted popup HTML
def create_popup_content(row):
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 300px;">
        <h3 style="color: #3366cc;">{row['Title']}</h3>
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="background-color: #f2f2f2;">
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Category:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{row['Category']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Date:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{row['Date']}</td>
            </tr>
            <tr style="background-color: #f2f2f2;">
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Location:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{row['City']}, {row['Country']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Casualty:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{row['Casualty']}</td>
            </tr>
            <tr style="background-color: #f2f2f2;">
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Injury:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{row['Injury']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Impact:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{row['Impact']}</td>
            </tr>
            <tr style="background-color: #f2f2f2;">
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Severity:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{row['Severity']}</td>
            </tr>
        </table>
        <p style="margin-top: 10px;">
            <a href="{row['Link']}" target="_blank" style="color: #3366cc; text-decoration: none;">Read More</a>
        </p>
    </div>
    """
    return html

# Main function
def main():
    st.set_page_config(layout="wide")
    st.title("CBRNE Incident Map")

    # Load data
    data = load_data()
    world = load_world()

    # Sidebar filters
    st.sidebar.header("Filters")
    type_filter = st.sidebar.multiselect("Type", data['Type'].unique())
    category_filter = st.sidebar.multiselect("Category", data['Category'].unique())
    country_filter = st.sidebar.multiselect("Country", data['Country'].unique())
    impact_filter = st.sidebar.multiselect("Impact", data['Impact'].unique())
    severity_filter = st.sidebar.multiselect("Severity", data['Severity'].unique())

    # Apply filters
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

    # Geocode locations
    filtered_data['Coordinates'] = filtered_data.apply(lambda row: geocode(f"{row['City']}, {row['Country']}"), axis=1)

    # Create map 1 (Incident Map)
    m = folium.Map(location=[0, 0], zoom_start=2)

    # Add country boundaries
    folium.GeoJson(
        world,
        style_function=lambda feature: {
            'fillColor': '#ffff00',
            'color': 'black',
            'weight': 2,
            'fillOpacity': 0.1,
        }
    ).add_to(m)

    # Add markers with different icons based on category
    for idx, row in filtered_data.iterrows():
        if row['Coordinates']:
            icon = folium.Icon(icon=get_marker_icon(row['Category']), prefix='fa')
            folium.Marker(
                location=row['Coordinates'],
                popup=folium.Popup(create_popup_content(row), max_width=350),
                tooltip=row['Title'],
                icon=icon
            ).add_to(m)

    # Display map 1
    st.subheader("Incident Map")
    folium_static(m, width=1200)

    # Create map 2 (Heatmap)
    st.subheader("Incident Heatmap")
    
    # Count links per country and city
    link_counts = filtered_data.groupby(['Country', 'City'])['Link'].count().reset_index()
    link_counts = link_counts.rename(columns={'Link': 'LinkCount'})

    # Merge link counts with coordinates
    heatmap_data = pd.merge(filtered_data, link_counts, on=['Country', 'City'])

    heat_data = heatmap_data[heatmap_data['Coordinates'].notna()][['Coordinates', 'LinkCount']]
    heat_data['lat'] = heat_data['Coordinates'].apply(lambda x: x[0])
    heat_data['lon'] = heat_data['Coordinates'].apply(lambda x: x[1])
    heat_data = heat_data[['lat', 'lon', 'LinkCount']].values.tolist()

    heatmap = folium.Map(location=[0, 0], zoom_start=2)
    HeatMap(heat_data).add_to(heatmap)
    folium_static(heatmap, width=1200)

    # Display filtered data
    st.subheader("Filtered Data")
    st.dataframe(filtered_data, width=1200)

if __name__ == "__main__":
    main()
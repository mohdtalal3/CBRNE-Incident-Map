import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim
import plotly.graph_objs as go
import random
import plotly.express as px


@st.cache_data
def load_data():
    data = pd.read_excel('News GIS.xlsx', engine='openpyxl')
    return data


@st.cache_data
def load_world():
    url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
    return gpd.read_file(url)


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


def get_marker_icon(category):
    icons = {
        'Explosive': 'bomb',
        'Biological': 'bug',
        'Radiological': 'radiation',
        'Chemical': 'flask',
        'Nuclear': 'atom'
    }
    return icons.get(category, 'info-sign')


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

def generate_random_colors(n):
    return [f"rgb({random.randint(0,255)}, {random.randint(0,255)}, {random.randint(0,255)})" for _ in range(n)]


def main():
    st.set_page_config(layout="wide")
    st.title("CBRNE Incident Map")


    data = load_data()
    world = load_world()

    
    data['Date'] = pd.to_datetime(data['Date'])

   
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


    filtered_data['Coordinates'] = filtered_data.apply(lambda row: geocode(f"{row['City']}, {row['Country']}"), axis=1)


    tab1, tab2, tab3 = st.tabs(["Incident Map", "Heatmap", "Data"])

    with tab1:
        st.subheader("Incident Map")
        
    
        col1, col2 = st.columns([2, 1])
        
        with col1:
           
            m = folium.Map(location=[0, 0], zoom_start=2, tiles="CartoDB dark_matter")

   
            folium.GeoJson(
                world,
                style_function=lambda feature: {
                    'fillColor': '#ffff00',
                    'color': 'white',
                    'weight': 1,
                    'fillOpacity': 0.1,
                }
            ).add_to(m)

   
            for idx, row in filtered_data.iterrows():
                if row['Coordinates']:
                    icon = folium.Icon(icon=get_marker_icon(row['Category']), prefix='fa')
                    folium.Marker(
                        location=row['Coordinates'],
                        popup=folium.Popup(create_popup_content(row), max_width=350),
                        tooltip=row['Title'],
                        icon=icon
                    ).add_to(m)

    
            folium_static(m, width=700, height=600)

        with col2:
            
            title_counts = filtered_data['Title'].value_counts().head(10)
            sources = title_counts.index.tolist()
            s_counts = title_counts.values.tolist()

            fig1 = go.Figure(data=[go.Bar(
                x=sources,
                y=s_counts,
                marker_color=generate_random_colors(len(sources))
            )])

            fig1.update_layout(
                title="Top 10 Incident Titles",
                yaxis_title="Count",
                xaxis_tickangle=-45,
                template="plotly_dark",
                showlegend=False,
                height=300  
            )
            fig1.update_xaxes(showticklabels=False)  

            st.plotly_chart(fig1, use_container_width=True)

            category_counts = filtered_data['Category'].value_counts()
            fig2 = px.pie(values=category_counts.values, names=category_counts.index, title="Incident Categories")
            fig2.update_layout(template="plotly_dark", height=300)  
            st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        st.subheader("Incident Heatmap")

    
        link_counts = filtered_data.groupby(['Country', 'City'])['Link'].count().reset_index()
        link_counts = link_counts.rename(columns={'Link': 'LinkCount'})
        heatmap_data = pd.merge(filtered_data, link_counts, on=['Country', 'City'])

        heat_data = heatmap_data[heatmap_data['Coordinates'].notna()][['Coordinates', 'LinkCount']]
        heat_data['lat'] = heat_data['Coordinates'].apply(lambda x: x[0])
        heat_data['lon'] = heat_data['Coordinates'].apply(lambda x: x[1])
        heat_data = heat_data[['lat', 'lon', 'LinkCount']].values.tolist()

        heatmap = folium.Map(location=[0, 0], zoom_start=2, tiles="CartoDB dark_matter")
        HeatMap(heat_data).add_to(heatmap)
        folium_static(heatmap, width=1200)

    with tab3:
        st.subheader("Filtered Data")
        st.dataframe(filtered_data, width=1200)

if __name__ == "__main__":
    main()
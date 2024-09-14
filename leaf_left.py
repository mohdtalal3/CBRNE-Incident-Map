import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim
import plotly.graph_objs as go
import random
import plotly.express as px
from fuzzywuzzy import process
from st_aggrid import AgGrid, GridOptionsBuilder
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from streamlit_plotly_events import plotly_events

from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from st_aggrid.shared import JsCode
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
    return data

def get_marker_icon(category):
    icons = {
        'Explosive': 'bomb',
        'Biological': 'bug',
        'Radiological': 'radiation',
        'Chemical': 'flask',
        'Nuclear': 'atom'
    }
    return icons.get(category, 'info-sign')

def get_marker_color(category):
    colors = {
        'Explosive': 'black',
        'Biological': 'green',
        'Radiological': 'red',
        'Chemical': 'orange',
        'Nuclear': 'blue'
    }
    return colors.get(category, 'gray')

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

from folium.plugins import MarkerCluster

def create_folium_map(filtered_data, world, selected_categories=None):
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

    marker_cluster = MarkerCluster(
        options={
            'spiderfyOnMaxZoom': True,
            'spiderLegPolylineOptions': {'weight': 1.5, 'color': '#222', 'opacity': 0.5},
            'zoomToBoundsOnClick': True
        }
    ).add_to(m)

    for idx, row in filtered_data.iterrows():
        if row['Coordinates'] and None not in row['Coordinates']:
            if selected_categories is None or row['Category'] in selected_categories:
                icon = folium.Icon(icon=get_marker_icon(row['Category']), 
                                   prefix='fa', 
                                   color=get_marker_color(row['Category']))
                
                folium.Marker(
                    location=row['Coordinates'],
                    popup=folium.Popup(create_popup_content(row), max_width=350),
                    tooltip=row['Title'],
                    icon=icon
                ).add_to(marker_cluster)

    return m
def create_heatmap(heat_data):
    heatmap = folium.Map(location=[0, 0], zoom_start=2, tiles="CartoDB dark_matter")
    HeatMap(heat_data).add_to(heatmap)
    return heatmap

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
    
    st.sidebar.header("Date Range")
    date_filter = st.sidebar.radio(
        "Select time range:",
        ("Past Day", "Past Week", "Past Month", "Past Year", "All Time", "Custom")
    )

    if date_filter == "Custom":
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input(
                "From date",
                value=data['Date'].min().date(),
                min_value=data['Date'].min().date(),
                max_value=data['Date'].max().date()
            )
        with col2:
            end_date = st.date_input(
                "To date",
                value=data['Date'].max().date(),
                min_value=data['Date'].min().date(),
                max_value=data['Date'].max().date()
            )
    else:
        end_date = pd.Timestamp.now().date()
        if date_filter == "Past Day":
            start_date = end_date - pd.Timedelta(days=1)
        elif date_filter == "Past Week":
            start_date = end_date - pd.Timedelta(weeks=1)
        elif date_filter == "Past Month":
            start_date = end_date - pd.Timedelta(days=30)
        elif date_filter == "Past Year":
            start_date = end_date - pd.Timedelta(days=365)
        else:  # All Time
            start_date = data['Date'].min().date()

    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    filtered_data = filter_data(data, type_filter, category_filter, country_filter, impact_filter, severity_filter, start_date, end_date, search_term)

    tab1, tab2, tab3 = st.tabs(["Incident Map", "Heatmap", "Data"])

    with tab1:
        st.subheader("Incident Map")
        
        # Create map
        selected_categories = st.session_state.get('selected_categories', None)
        m = create_folium_map(filtered_data, world, selected_categories)
        
        # Display  map
        folium_static(m, width=1400, height=500)
        
        # Create and display pie chart
        category_counts = filtered_data['Category'].value_counts()
        fig1 = px.pie(values=category_counts.values, names=category_counts.index, title="Distribution by Category")
        fig1.update_layout(template="plotly_dark", height=400)
        
        selected_points = plotly_events(fig1, click_event=True, hover_event=False)
        if selected_points:
            selected_category = category_counts.index[selected_points[0]['pointNumber']]
            st.session_state['selected_categories'] = [selected_category]
        elif 'selected_categories' in st.session_state:
            del st.session_state['selected_categories']

        # Create bar chart for country distribution
        country_counts = filtered_data['Country'].value_counts().reset_index()
        country_counts.columns = ['Country', 'Count']

        # Define a custom color sequence
        color_sequence = px.colors.qualitative.Set3  # You can choose other color scales as well

        fig2 = px.bar(country_counts, x='Country', y='Count', 
                    title="Distribution by Country",
                    color='Country',  # This will assign a unique color to each country
                    color_discrete_sequence=color_sequence)  # Use the custom color sequence

        fig2.update_layout(
            template="plotly_dark", 
            height=400, 
            xaxis_title="Countries", 
            yaxis_title="Count",
            showlegend=False,
            xaxis_tickangle=45,
            hovermode="closest",
            xaxis=dict(showticklabels=False)  # Remove country names from x-axis
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

        link_counts = filtered_data.groupby(['Country', 'City'])['Link'].count().reset_index()
        link_counts = link_counts.rename(columns={'Link': 'LinkCount'})
        heatmap_data = pd.merge(filtered_data, link_counts, on=['Country', 'City'])

        heat_data = heatmap_data[heatmap_data['Coordinates'].notna()][['Coordinates', 'LinkCount']]
        heat_data['lat'] = heat_data['Coordinates'].apply(lambda x: x[0])
        heat_data['lon'] = heat_data['Coordinates'].apply(lambda x: x[1])
        heat_data = heat_data[['lat', 'lon', 'LinkCount']].values.tolist()

        heatmap = create_heatmap(heat_data)
        folium_static(heatmap, width=1400)


    with tab3:
        st.subheader("Filtered Data")
        display_columns = ['Title', 'Country', 'City', 'Date', 'Casualty', 'Injury', 'Impact', 'Severity', 'Link']
        df_display = filtered_data[display_columns].copy()
        df_display['Date'] = df_display['Date'].dt.date

        # Add export button
        csv = df_display.to_csv(index=False)
        st.download_button(
            label="Export Data",
            data=csv,
            file_name="filtered_data.csv",
            mime="text/csv",
        )

        gb = GridOptionsBuilder.from_dataframe(df_display, editable=True)

        gb.configure_column("Title", minWidth=400)
        gb.configure_column("Country", minWidth=250)
        gb.configure_column("City", minWidth=200)
        gb.configure_column("Date", minWidth=200)
        gb.configure_column("Impact", minWidth=200)
        gb.configure_column("Casualty", minWidth=50)
        gb.configure_column("Injury", minWidth=50)
        gb.configure_column('Link', minWidth=100)
        gb.configure_column("Severity", minWidth=200)
        
        gb.configure_column(
            "Link",
            headerName="Link",
            cellRenderer=JsCode("""
                class UrlCellRenderer {
                init(params) {
                    this.eGui = document.createElement('a');
                    this.eGui.innerText = 'Link';
                    this.eGui.setAttribute('href', params.value);
                    this.eGui.setAttribute('style', "text-decoration:none");
                    this.eGui.setAttribute('target', "_blank");
                }
                getGui() {
                    return this.eGui;
                }
                }
            """)
            )

        grid_options = gb.build()

        AgGrid(
            df_display,
            gridOptions=grid_options,
            updateMode=GridUpdateMode.VALUE_CHANGED,
            allow_unsafe_jscode=True,
            height=400,
            theme="streamlit",
            fit_columns_on_grid_load=True,
        )

if __name__ == "__main__":
    main()
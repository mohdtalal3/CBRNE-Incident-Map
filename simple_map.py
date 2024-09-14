import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
import plotly.express as px
from geopy.geocoders import Nominatim
from fuzzywuzzy import process
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from st_aggrid.shared import JsCode
from streamlit_plotly_events import plotly_events
from plotly.subplots import make_subplots
import numpy as np
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
    return colors.get(category, 'purple')  

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

def create_plotly_map(filtered_data, selected_categories=None):
    if selected_categories:
        filtered_data = filtered_data[filtered_data['Category'].isin(selected_categories)]

    fig = go.Figure()

    # Group data by category
    grouped_by_category = filtered_data.groupby('Category')

    for category, group in grouped_by_category:
        # Group data by coordinates within each category
        grouped_by_coords = group.groupby('Coordinates')
        
        lats, lons, texts, custom_data, sizes = [], [], [], [], []
        line_lats, line_lons = [], []
        
        for coords, coord_group in grouped_by_coords:
            lat, lon = coords
            if len(coord_group) == 1:
                # Single point
                row = coord_group.iloc[0]
                lats.append(lat)
                lons.append(lon)
                texts.append(create_popup_content(row))
                custom_data.append(row['Title'])
                sizes.append(10)
            else:
                # Multiple points at the same location
                radius = 1  # Adjust this value to change the size of the spider legs
                angles = np.linspace(0, 2*np.pi, len(coord_group), endpoint=False)
                
                # Add center point
                lats.append(lat)
                lons.append(lon)
                texts.append(f"Cluster of {len(coord_group)} incidents")
                custom_data.append(f"Cluster of {len(coord_group)} incidents")
                sizes.append(15)  # Larger size for cluster points
                
                for idx, (_, row) in enumerate(coord_group.iterrows()):
                    spider_lat = lat + radius * np.cos(angles[idx])
                    spider_lon = lon + radius * np.sin(angles[idx])
                    
                    lats.append(spider_lat)
                    lons.append(spider_lon)
                    texts.append(create_popup_content(row))
                    custom_data.append(row['Title'])
                    sizes.append(8)  # Smaller size for individual points in a cluster

                    # Add lines for spider legs
                    line_lats.extend([lat, spider_lat, None])
                    line_lons.extend([lon, spider_lon, None])

        # Add markers
        fig.add_trace(go.Scattermapbox(
            lat=lats,
            lon=lons,
            mode='markers',
            marker=go.scattermapbox.Marker(
                size=sizes,
                color=get_marker_color(category),
                opacity=0.7
            ),
            text=texts,
            hoverinfo='text',
            name=category,
            customdata=custom_data,
            showlegend=True
        ))

        # Add lines (spider legs)
        fig.add_trace(go.Scattermapbox(
            lat=line_lats,
            lon=line_lons,
            mode='lines',
            line=dict(width=1, color=get_marker_color(category)),
            hoverinfo='skip',
            showlegend=False
        ))

    fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=20, lon=0),
            zoom=1.5,
        ),
        showlegend=True,
        legend_title_text='Category',
        height=600,
        margin={"r":0,"t":0,"l":0,"b":0},
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
        
        # Map
        selected_categories = st.session_state.get('selected_categories', None)
        fig = create_plotly_map(filtered_data, selected_categories)
        st.plotly_chart(fig, use_container_width=True)

        # Pie chart
        category_counts = filtered_data['Category'].value_counts()
        fig1 = px.pie(values=category_counts.values, names=category_counts.index, title="Distribution by Category")
        fig1.update_layout(template="plotly_dark", height=400)
        
        selected_points = plotly_events(fig1, click_event=True, hover_event=False)
        if selected_points:
            selected_category = category_counts.index[selected_points[0]['pointNumber']]
            st.session_state['selected_categories'] = [selected_category]
        elif 'selected_categories' in st.session_state:
            del st.session_state['selected_categories']
        
        #st.plotly_chart(fig1, use_container_width=True)

        # Distribution chart
        country_counts = filtered_data['Country'].value_counts().reset_index()
        country_counts.columns = ['Country', 'Count']

        color_sequence = px.colors.qualitative.Set3

        fig2 = px.bar(country_counts, x='Country', y='Count', 
                    title="Distribution by Country",
                    color='Country',
                    color_discrete_sequence=color_sequence)

        fig2.update_layout(
            template="plotly_dark", 
            height=400, 
            xaxis_title="Countries", 
            yaxis_title="Count",
            showlegend=False,
            xaxis_tickangle=45,
            hovermode="closest",
            xaxis=dict(showticklabels=False)
        )
        fig2.update_traces(
            hovertemplate="<b>%{x}</b><br>Count: %{y}"
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Trend chart
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
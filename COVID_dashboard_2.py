# Streamlit live coding script
import streamlit as st
import pandas as pd
import numpy as np
import requests, zipfile, io
import plotly.graph_objs as go
from datetime import datetime, timedelta
import json

# st.set_page_config(layout="wide")


# Data importing
# Heroku files path!!!
# ./data/raw/stzh.adm_stadtkreise_a.json
# ./data/raw/20200306_hundehalter.csv
# dogs_geojson = json.load(open("./data/raw/stzh.adm_stadtkreise_a.json"))
# dog_df = pd.read_csv("./data/raw/20200306_hundehalter.csv")

##############
# Functions #
#############

# Data Cleaning:
def clean_daily(df):
    clean_df = df[['geoRegion','datum','entries']]
    clean_df['7-day_avg']= clean_df['entries'].rolling(window=7,min_periods=7,center=True).mean()
    clean_df['7-day_avg'] = clean_df['7-day_avg'].round(2)
    clean_df['datum'] = pd.to_datetime(clean_df['datum'], format='%Y-%m-%d').dt.date
    return clean_df

def clean_age(df):
    df_age = df[['altersklasse_covid19','geoRegion','datum_dboardformated','entries']]
    df_age = df_age.drop(df_age[df_age['altersklasse_covid19']=='Unbekannt'].index)
    df_age = df_age.set_index(['datum_dboardformated','geoRegion','altersklasse_covid19'])
    df_age = df_age.unstack()
    df_age.columns = df_age.columns.to_series().str.join('_')
    df_age = df_age.reset_index()
    df_age = df_age.rename(columns={'datum_dboardformated':'datum','entries_0 - 9':'0 - 9','entries_10 - 19':'10 - 19',
                                             'entries_20 - 29':'20 - 29','entries_30 - 39':'30 - 39','entries_40 - 49':'40 - 49',
                                             'entries_50 - 59':'50 - 59','entries_60 - 69':'60 - 69','entries_70 - 79':'70 - 79',
                                             'entries_80+':'80+'})
    df_age['datum'] = df_age['datum'].apply(lambda row: datetime.strptime(row + '-1', "%Y-%W-%w")+ pd.offsets.Day(-7) if '2020' in row else datetime.strptime(row + '-1', "%Y-%W-%w"))
    df_age['datum'] = pd.to_datetime(df_age['datum'], format='%Y-%m-%d').dt.date

    return df_age

def clean_datasex(df):
    df_sexcases = df[['sex', 'geoRegion', 'datum_dboardformated', 'entries']]

    df_sexcases = df_sexcases.drop(df_sexcases[df_sexcases['sex'] == 'unknown'].index)
    df_sexcases = df_sexcases.set_index(['datum_dboardformated', 'geoRegion', 'sex'])
    df_sexcases = df_sexcases.unstack()

    df_sexcases.columns = df_sexcases.columns.to_series().str.join('_')
    df_sexcases = df_sexcases.reset_index()

    df_sexcases = df_sexcases.rename(
        columns={'datum_dboardformated': 'datum', 'entries_female': 'female', 'entries_male': 'male'})

    df_sexcases['datum'] = df_sexcases['datum'].apply(
        lambda row: datetime.strptime(row + '-1', "%Y-%W-%w") + pd.offsets.Day(
            -7) if '2020' in row else datetime.strptime(row + '-1', "%Y-%W-%w"))

    df_sexcases['datum'] = pd.to_datetime(df_sexcases['datum'], format='%Y-%m-%d').dt.date

    df_sexcases['total'] = df_sexcases['female'] + df_sexcases['male']
    df_sexcases['p_female'] = df_sexcases['female'] / df_sexcases['total']
    df_sexcases['p_male'] = df_sexcases['male'] / df_sexcases['total']

    df_sexcases['p_male'] = df_sexcases['p_male'].fillna(0)
    df_sexcases['p_female'] = df_sexcases['p_female'].fillna(0)

    df_sexcases['p_female'] = df_sexcases['p_female'].round(2)
    df_sexcases['p_male'] = df_sexcases['p_male'].round(2)

    # df_sexcases['p_female'] = df_sexcases['p_female'].apply(lambda x: '{0:.0f}%'.format(x*100))
    # df_sexcases['p_male'] = df_sexcases['p_male'].apply(lambda x: '{0:.0f}%'.format(x*100))
    # df_sexcases['p_total'] = df_sexcases['p_male'] + df_sexcases['p_female']
    return df_sexcases

# Graphs:
def gen_graph(df,region,plot_type,plot_time):
    date = dict_time[plot_time]
    df_region = df[df['datum']>=dict_time[plot_time]]
    df_region = df_region[df_region['geoRegion']==region]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_region['datum'], y=df_region['entries'], name=plot_type,marker_color='#1f77b4'))
    fig.add_trace(go.Scatter(x=df_region['datum'], y=df_region['7-day_avg'], name='7-day Avg',marker_color='red'))
    fig.update_layout(
                hovermode="x unified",
                legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1),
                autosize=False,
                width=900,
                height=600,
                plot_bgcolor="white",
                xaxis={"title": {"text": "Date", "font": {"size": 16}}},
                yaxis={"title": {"text": "Daily Cases", "font": {"size": 16}}},
                title = {'text': 'Development over time in {}'.format(region), "font": {"size": 24}})

    return fig

def gen_heatmap(df,region,plot_type,plot_time):
    date = dict_time[plot_time]
    df_age_region = df[df['datum']>=dict_time[plot_time]]
    df_age_region = df_age_region[df_age_region['geoRegion'] == region]
    x = df_age_region['datum'].to_numpy()
    z = df_age_region[['0 - 9', '10 - 19', '20 - 29', '30 - 39', '40 - 49', '50 - 59', '60 - 69', '70 - 79', '80+']].to_numpy()

    fig2 = go.Figure(data=go.Heatmap(
        z=z.T,
        x=x,
        y=['0 - 9', '10 - 19', '20 - 29', '30 - 39', '40 - 49', '50 - 59', '60 - 69', '70 - 79', '80+']))
    fig2.update_layout(autosize=False,width=900,height=400,title = {'text': 'Distribution by Age Group in {}'.format(region), "font": {"size": 24}})
    fig2.update_traces(colorscale='blues', ygap=3, selector=dict(type='heatmap'))
    return fig2


def gen_sexmap(df,region,plot_type,plot_time):
    date = dict_time[plot_time]
    df_sex_region = df[df['datum'] >= dict_time[plot_time]]
    df_sex_region = df_sex_region[df_sex_region['geoRegion'] == region]

    fig3 = go.Figure()
    fig3.add_trace(go.Bar(x=df_sex_region["datum"], y=df_sex_region['p_female'], name='Female', marker_color='#9EB9F3'))
    fig3.add_trace(go.Bar(x=df_sex_region["datum"], y=df_sex_region['p_male'], name='Male', marker_color='#1f77b4'))
    fig3.add_hline(y=0.5, line_dash="dot",
                  line_color="white", line_width=2,
                  name='50%'
                  )
    fig3.update_layout(
                barmode='stack',
                hovermode="x unified",
                legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1),
                autosize=False,
                width=900,
                height=400,
                title = {'text': 'Distribution by Gender in {}'.format(region), "font": {"size": 24}})
    return fig3

#################
# Data Loading: #
#################

r = requests.get("https://www.covid19.admin.ch/api/data/20211227-7cmpljm9/downloads/sources-csv.zip")
z = zipfile.ZipFile(io.BytesIO(r.content))

dailycases_csv = z.open("data/COVID19Cases_geoRegion.csv") #Total Daily Cases by Canton
df_dailycases = pd.read_csv(dailycases_csv)

dailydeaths_csv = z.open("data/COVID19Death_geoRegion.csv") #Total Daily Deaths by Canton
df_dailydeaths = pd.read_csv(dailydeaths_csv)

dailyhosp_csv = z.open("data/COVID19Hosp_geoRegion.csv") #Total Daily Hospitalizations by Canton
df_dailyhosp = pd.read_csv(dailyhosp_csv)

agecases_csv = z.open("data/COVID19Cases_geoRegion_AKL10_w.csv") #Total Daily Cases by Age Group
df_agecases = pd.read_csv(agecases_csv)

agedeaths_csv = z.open("data/COVID19Death_geoRegion_AKL10_w.csv") #Total Daily Deaths by Age Group
df_agedeaths = pd.read_csv(agedeaths_csv)

agehosp_csv = z.open("data/COVID19Hosp_geoRegion_AKL10_w.csv") #Total Daily Deaths by Age Group
df_agehosp = pd.read_csv(agehosp_csv)

sexcases_csv = z.open("data/COVID19Cases_geoRegion_sex_w.csv") #Total Daily Cases by Gender Group
df_sexcases = pd.read_csv(sexcases_csv)

sexdeaths_csv = z.open("data/COVID19Death_geoRegion_sex_w.csv") #Total Daily Cases by Gender Group
df_sexdeaths = pd.read_csv(sexdeaths_csv)

sexhosp_csv = z.open("data/COVID19Hosp_geoRegion_sex_w.csv") #Total Daily Cases by Gender Group
df_sexhosp = pd.read_csv(sexhosp_csv)

j = requests.get("https://www.covid19.admin.ch/api/data/20211227-7cmpljm9/downloads/sources-json.zip")
js = zipfile.ZipFile(io.BytesIO(j.content))

json_file = js.open("data/COVID19Cases_geoRegion.json") #Json File for Canton Information
json_dailycases = json.load(json_file)

df_dailycases = clean_daily(df_dailycases)
df_dailydeaths = clean_daily(df_dailydeaths)
df_dailyhosp = clean_daily(df_dailyhosp)

cantons = df_dailycases['geoRegion'].unique().tolist()

df_agecases = clean_age(df_agecases)
df_agedeaths = clean_age(df_agedeaths)
df_agehosp = clean_age(df_agehosp)

df_sexcases = clean_datasex(df_sexcases)
df_sexdeaths = clean_datasex(df_sexdeaths)
df_sexhosp = clean_datasex(df_sexhosp)

# Preparing Variables for Dropdown Menus
time = ['All time','2 weeks','30 days','3 months','6 months']
plot_type = ['New Cases','Deaths','Hospitalizations']

first_day = min(df_dailycases['datum'])
last_day = max(df_dailycases['datum'])
two_weeks = last_day - timedelta(15)
one_month = last_day - timedelta(30)
three_months = last_day - timedelta(90)
six_months = last_day - timedelta(180)

dict_time = {time[0]:first_day,time[1]:two_weeks,time[2]:one_month,time[3]:three_months,time[4]:six_months}

plot_type = st.sidebar.selectbox("Check Case Type:", plot_type)
plot_region = st.sidebar.selectbox("Check the Canton:", cantons)
plot_time = st.sidebar.selectbox("Check the time range:", time)

#############
# Streamlit #
#############

st.title("Covid19-Switzerland")

if plot_type=='Deaths':
    st.header('Laboratory-confirmed deaths')
    st.write('People who have died with a laboratory-confirmed COVID-19 infection. For this statistic the date of death is decisive.  \n'
             'The graph shows the development of deaths for the selected time frame.  \n*(Absolute numbers)*')

    st.plotly_chart(gen_graph(df_dailydeaths,plot_region,plot_type,plot_time))
    st.plotly_chart(gen_heatmap(df_agedeaths, plot_region, plot_type, plot_time))
    st.plotly_chart(gen_sexmap(df_sexdeaths, plot_region, plot_type, plot_time))
elif plot_type=='New Cases':
    st.header('Laboratory-confirmed cases')
    st.write('The graph shows the development of laboratory-confirmed cases for the selected time frame.  \n*(Absolute numbers)*')
    st.plotly_chart(gen_graph(df_dailycases,plot_region,plot_type,plot_time))
    st.plotly_chart(gen_heatmap(df_agecases, plot_region, plot_type, plot_time))
    st.plotly_chart(gen_sexmap(df_sexcases, plot_region, plot_type, plot_time))
elif plot_type=='Hospitalizations':
    st.header('Laboratory-confirmed hospitalisations')
    st.write('The graph shows the development of hospitalisation admissions for the selected time frame.  \n*(Absolute numbers)*')
    st.plotly_chart(gen_graph(df_dailyhosp,plot_region,plot_type,plot_time))
    st.plotly_chart(gen_heatmap(df_agehosp, plot_region, plot_type, plot_time))
    st.plotly_chart(gen_sexmap(df_sexhosp, plot_region, plot_type, plot_time))

st.write('Data Source: [Federal Office of Public Health FOPH](https://www.covid19.admin.ch/en/overview)')
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
import plotly.express as px  # <-- La nueva magia visual

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="AF Seguros | Rendimiento", page_icon="🛡️", layout="wide")

ocultar_estilo = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(ocultar_estilo, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS ---
@st.cache_data(ttl=600) 
def cargar_datos_completos():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        
        # --- NUEVA LÓGICA DE DETECCIÓN (LOCAL VS NUBE) ---
        ruta_actual = os.path.dirname(os.path.abspath(__file__))
        ruta_json = os.path.join(ruta_actual, 'credenciales_google.json')
        
        # 1. Verificamos si el archivo físico existe (Estamos en tu PC local)
        if os.path.exists(ruta_json):
            credenciales = Credentials.from_service_account_file(ruta_json, scopes=scopes)
        # 2. Si el archivo no existe (Estamos en la Nube de Streamlit)
        else:
            credenciales = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
            
        cliente = gspread.authorize(credenciales)
        
        # ⚠️ AQUÍ DEBES PEGAR TU URL DEL EXCEL DE AF SEGUROS DE NUEVO
        url_excel = 'https://docs.google.com/spreadsheets/d/1EfwZDbo8ZzAthOqdcLp3FMrZW10BRWKpbADqknlI470/edit'
        hoja_calculo = cliente.open_by_url(url_excel) 
        
        pestana_historico = hoja_calculo.worksheet('Historico_API')
        datos_hist = pestana_historico.get_all_values()
        df_hist = pd.DataFrame()
        if datos_hist:
            df_hist = pd.DataFrame(datos_hist, columns=['Fecha', 'Metrica', 'Valor'])
            df_hist = df_hist[df_hist['Fecha'] != 'Fecha']
            df_hist['Valor'] = pd.to_numeric(df_hist['Valor'], errors='coerce').fillna(0)
            df_hist['Fecha'] = pd.to_datetime(df_hist['Fecha'])

        pestana_posts = hoja_calculo.worksheet('Top_Posts')
        datos_posts = pestana_posts.get_all_values()
        df_posts = pd.DataFrame()
        if len(datos_posts) > 1: 
            df_posts = pd.DataFrame(datos_posts[1:], columns=datos_posts[0])
            df_posts['Likes'] = pd.to_numeric(df_posts['Likes'], errors='coerce').fillna(0)
            df_posts['Comentarios'] = pd.to_numeric(df_posts['Comentarios'], errors='coerce').fillna(0)
            
        return df_hist, df_posts
    except Exception as e:
        st.error(f"Fallo técnico detectado: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- 3. INTERFAZ VISUAL ---
st.title("📈 Panel de Rendimiento Orgánico")
st.markdown("**Cliente:** AF Seguros | **Desarrollado por:** Agencia Bitácora")
st.markdown("---")

df_hist, df_posts = cargar_datos_completos()

if df_hist.empty and df_posts.empty:
    st.info("⏳ Esperando datos... Asegúrate de haber corrido el extractor de Meta.")
else:
    # --- CREACIÓN DE LAS PESTAÑAS (TABS) ---
    tab1, tab2 = st.tabs(["📊 Resumen General", "🏆 Top Performance"])

    # --- PESTAÑA 1: KPIs y Gráficas ---
    with tab1:
        if not df_hist.empty:
            ultima_fecha = df_hist['Fecha'].max()
            datos_recientes = df_hist[df_hist['Fecha'] == ultima_fecha]
            
            alcance_hoy = datos_recientes[datos_recientes['Metrica'] == 'reach']['Valor'].sum()
            vistas_hoy = datos_recientes[datos_recientes['Metrica'] == 'profile_views']['Valor'].sum()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Alcance Diario (Reach)", value=f"{int(alcance_hoy):,}")
            with col2:
                st.metric(label="Vistas del Perfil", value=f"{int(vistas_hoy):,}")
            with col3:
                st.metric(label="Última Actualización", value=ultima_fecha.strftime('%Y-%m-%d'))

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("Tendencia de Crecimiento")
            
            # --- NUEVA GRÁFICA INTERACTIVA CON PLOTLY ---
            df_grafico = df_hist.pivot_table(index='Fecha', columns='Metrica', values='Valor', aggfunc='sum')
            
            fig = px.line(
                df_grafico, 
                x=df_grafico.index, 
                y=df_grafico.columns,
                markers=True, # Le pone puntitos a la línea
                color_discrete_sequence=['#0047AB', '#00C49F'] # Colores más corporativos
            )
            # Limpiamos el fondo para que se vea minimalista
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", 
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis_title="", 
                yaxis_title="",
                hovermode="x unified" # Hace que una línea siga tu mouse
            )
            # Le quitamos la cuadrícula fea
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(showgrid=True, gridcolor='lightgray')
            
            st.plotly_chart(fig, use_container_width=True)

    # --- PESTAÑA 2: Ranking de Posts ---
    with tab2:
        if not df_posts.empty:
            st.subheader("🏆 Ranking de Publicaciones")
            df_posts_ordenado = df_posts.sort_values(by="Likes", ascending=False).reset_index(drop=True)
            
            st.dataframe(
                df_posts_ordenado,
                column_config={
                    "Link": st.column_config.LinkColumn("Ir al Post (Clic aquí)"),
                    "Likes": st.column_config.NumberColumn("❤️ Likes", format="%d"),
                    "Comentarios": st.column_config.NumberColumn("💬 Comentarios", format="%d")
                },
                use_container_width=True,
                hide_index=True 
            )

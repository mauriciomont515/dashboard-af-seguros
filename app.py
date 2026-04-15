import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
import plotly.express as px

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
        
        ruta_actual = os.path.dirname(os.path.abspath(__file__))
        ruta_json = os.path.join(ruta_actual, 'credenciales_google.json')
        
        if os.path.exists(ruta_json):
            credenciales = Credentials.from_service_account_file(ruta_json, scopes=scopes)
        else:
            credenciales = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
            
        cliente = gspread.authorize(credenciales)
        
        # ⚠️ AQUÍ DEBES PEGAR TU URL DEL EXCEL DE AF SEGUROS
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
            # NUEVO: Convertimos la fecha de los posts a formato calendario
            df_posts['Fecha'] = pd.to_datetime(df_posts['Fecha'], errors='coerce') 
            
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
    # --- NUEVO: SISTEMA DE FILTRADO DE FECHAS ---
    # Sacamos la fecha más vieja y la más nueva para ponerlas de límite
    min_date = df_hist['Fecha'].min().date()
    max_date = df_hist['Fecha'].max().date()

    col_calendario, col_espacio = st.columns([1, 2]) # Hace que el calendario no ocupe toda la pantalla
    with col_calendario:
        rango_fechas = st.date_input(
            "🗓️ Rango de Análisis",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

    # Lógica: Si el usuario seleccionó inicio y fin, podamos los datos
    if len(rango_fechas) == 2:
        fecha_inicio, fecha_fin = rango_fechas
        fecha_inicio = pd.to_datetime(fecha_inicio)
        fecha_fin = pd.to_datetime(fecha_fin)
        
        df_hist_filt = df_hist[(df_hist['Fecha'] >= fecha_inicio) & (df_hist['Fecha'] <= fecha_fin)]
        df_posts_filt = df_posts[(df_posts['Fecha'] >= fecha_inicio) & (df_posts['Fecha'] <= fecha_fin)]
    else:
        df_hist_filt = df_hist
        df_posts_filt = df_posts

    st.markdown("<br>", unsafe_allow_html=True) # Un saltico de línea para respirar

    # --- TABS CON DATOS FILTRADOS ---
    tab1, tab2 = st.tabs(["📊 Resumen General", "🏆 Top Performance"])

    with tab1:
        if not df_hist_filt.empty:
            # 1. Totales del periodo actual
            alcance_periodo = int(df_hist_filt[df_hist_filt['Metrica'] == 'reach']['Valor'].sum())
            vistas_periodo = int(df_hist_filt[df_hist_filt['Metrica'] == 'profile_views']['Valor'].sum())

            # 2. LA MAGIA MATEMÁTICA: Viaje al pasado para comparar
            delta_alcance = 0
            delta_vistas = 0
            porcentaje_alcance = 0
            dias_analizados = (df_hist_filt['Fecha'].max() - df_hist_filt['Fecha'].min()).days + 1
            
            if len(rango_fechas) == 2:
                fecha_fin_prev = pd.to_datetime(rango_fechas[0]) - pd.Timedelta(days=1)
                fecha_inicio_prev = fecha_fin_prev - pd.Timedelta(days=dias_analizados - 1)
                
                df_hist_prev = df_hist[(df_hist['Fecha'] >= fecha_inicio_prev) & (df_hist['Fecha'] <= fecha_fin_prev)]
                
                if not df_hist_prev.empty:
                    alcance_prev = int(df_hist_prev[df_hist_prev['Metrica'] == 'reach']['Valor'].sum())
                    vistas_prev = int(df_hist_prev[df_hist_prev['Metrica'] == 'profile_views']['Valor'].sum())
                    
                    delta_alcance = alcance_periodo - alcance_prev
                    delta_vistas = vistas_periodo - vistas_prev
                    
                    if alcance_prev > 0:
                        porcentaje_alcance = (delta_alcance / alcance_prev) * 100

            # 3. INTERFAZ: Las Flechitas de la Tranquilidad
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    label="Alcance Total (Periodo)", 
                    value=f"{alcance_periodo:,}", 
                    delta=f"{delta_alcance:,} vs periodo anterior" if delta_alcance != 0 else None,
                    help="Cantidad de personas únicas que vieron tu contenido."
                )
            with col2:
                st.metric(
                    label="Vistas del Perfil", 
                    value=f"{vistas_periodo:,}", 
                    delta=f"{delta_vistas:,} vs periodo anterior" if delta_vistas != 0 else None,
                    help="Veces que entraron a ver tu perfil de Instagram."
                )
            with col3:
                st.metric(label="Días Analizados", value=f"{dias_analizados}")

            st.markdown("<br>", unsafe_allow_html=True)
            
            # 4. EL TRADUCTOR BITÁCORA (Insight Automático)
            st.subheader("💡 Resumen Ejecutivo")
            
            # Lógica para definir si el texto es de felicitación o de alerta
            tendencia = "un aumento" if delta_alcance > 0 else "una disminución" if delta_alcance < 0 else "un mantenimiento"
            color_caja = "success" if delta_alcance >= 0 else "warning"
            
            mensaje = f"Durante los últimos **{dias_analizados} días**, la marca AF Seguros ha logrado aparecer en la pantalla de **{alcance_periodo:,} personas**. Esto representa **{tendencia} del {abs(porcentaje_alcance):.1f}%** frente al periodo inmediatamente anterior. La estrategia de posicionamiento orgánico está en marcha."
            
            if color_caja == "success":
                st.success(mensaje)
            else:
                st.warning(mensaje)

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("Tendencia de Crecimiento")
            
            # ... (AQUÍ SIGUE TU CÓDIGO INTACTO DE LA GRÁFICA FIG = PX.LINE...)
            
            df_grafico = df_hist_filt.pivot_table(index='Fecha', columns='Metrica', values='Valor', aggfunc='sum')
            
            fig = px.line(
                df_grafico, x=df_grafico.index, y=df_grafico.columns,
                markers=True, color_discrete_sequence=['#0047AB', '#00C49F']
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis_title="", yaxis_title="", hovermode="x unified"
            )
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(showgrid=True, gridcolor='lightgray')
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No hay datos de métricas generales para este rango de fechas.")

# --- PESTAÑA 2: Ranking de Posts ---
    with tab2:
        if not df_posts_filt.empty:
            st.subheader("🏆 Ranking de Publicaciones (Top Performance)")
            
            # Hacemos una copia de los datos filtrados
            df_posts_ordenado = df_posts_filt.copy()
            
            # 1. LA MAGIA MATEMÁTICA: Sumamos Likes + Comentarios
            df_posts_ordenado['Interacciones'] = df_posts_ordenado['Likes'] + df_posts_ordenado['Comentarios']
            
            # 2. Ordenamos el ranking usando esta nueva métrica súper poderosa
            df_posts_ordenado = df_posts_ordenado.sort_values(by="Interacciones", ascending=False).reset_index(drop=True)
            df_posts_ordenado['Fecha'] = df_posts_ordenado['Fecha'].dt.strftime('%Y-%m-%d')
            
            # 3. Sacamos el récord máximo para calibrar la barra de progreso
            max_interacciones = int(df_posts_ordenado['Interacciones'].max())
            
            # 4. Inyectamos la tabla con la nueva barra visual
            st.dataframe(
                df_posts_ordenado,
                column_config={
                    "Link": st.column_config.LinkColumn("Ir al Post"),
                    "Likes": st.column_config.NumberColumn("❤️ Likes", format="%d"),
                    "Comentarios": st.column_config.NumberColumn("💬 Coment.", format="%d"),
                    "Interacciones": st.column_config.ProgressColumn(
                        "🔥 Impacto Total",
                        help="Suma de Likes y Comentarios. La barra muestra el nivel frente al post más exitoso.",
                        format="%d",
                        min_value=0,
                        max_value=max_interacciones
                    )
                },
                use_container_width=True,
                hide_index=True 
            )
        else:
            st.warning("No se encontraron publicaciones en este rango de fechas.")

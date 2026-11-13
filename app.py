import streamlit as st
import requests
import pandas as pd
import altair as alt
import time

# Настройка страницы
st.set_page_config(page_title="Парсер вакансий РФ", page_icon="💼", layout="wide")

st.title("💼 Мониторинг и парсер вакансий в РФ")
st.caption("Приложение собирает актуальные данные напрямую через официальное и открытое API «Работа России»")

# Боковая панель с фильтрами
st.sidebar.header("🔍 Параметры поиска")
search_query = st.sidebar.text_input("Ключевое слово (например, Python)", "Системный аналитик")
limit_vacancies = st.sidebar.slider("Количество вакансий для загрузки", 20, 100, 40, step=20)
only_with_salary = st.sidebar.checkbox("Только с указанием зарплаты", value=False)

# Настройка сортировки по зарплате
sort_order = st.sidebar.selectbox(
    "Сортировка по зарплате",
    options=["Без сортировки", "По убыванию (сначала дорогие)", "По возрастанию"]
)

@st.cache_data(ttl=600, show_spinner=False)
def fetch_vacancies_trudvsem(query, limit):
    url = "http://opendata.trudvsem.ru/api/v1/vacancies"
    all_vacancies = []
    
    params = {
        "text": query,
        "limit": limit
    }
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    results = data.get("results", {}).get("vacancies", [])
                except ValueError:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    st.error("Сервер «Работа России» временно отдает HTML вместо JSON. Попробуйте нажать кнопку еще раз через 10-15 секунд.")
                    break
                
                for item in results:
                    v = item.get("vacancy", {})
                    sal_from = v.get("salary_min")
                    sal_to = v.get("salary_max")
                    
                    if sal_from == 0 and sal_to == 0:
                        sal_from, sal_to = None, None
                    
                    region_name = v.get("region", {}).get("name", "Не указано")
                    
                    all_vacancies.append({
                        "name": v.get("job-name"),
                        "employer": v.get("company", {}).get("name", "Не указано"),
                        "area": region_name,
                        "salary_from": sal_from,
                        "salary_to": sal_to,
                        "experience": str(v.get("experience", "Не указано")),
                        "employment": v.get("employment", "Полная"),
                        "alternate_url": v.get("vac_url")
                    })
                return all_vacancies[:limit]
                
            elif response.status_code == 429:
                if attempt < max_retries - 1:
                    st.warning(f"Сервер перегружен (429). Ожидание {retry_delay} сек. и повторная попытка...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    st.error("Превышен лимит запросов к ТрудВсем. Пожалуйста, подождите 1 минуту.")
            else:
                st.error(f"Ошибка сервера ТрудВсем: {response.status_code}")
                break
                
        except Exception as e:
            st.error(f"Ошибка подключения: {e}")
            break
            
    return all_vacancies

def process_data(vacancies, with_salary):
    processed = []
    for v in vacancies:
        frm = v["salary_from"]
        to = v["salary_to"]
        
        if with_salary and frm is None and to is None:
            continue
            
        if frm and to and frm != to:
            salary_str = f"от {int(frm)} до {int(to)} руб."
        elif frm:
            salary_str = f"от {int(frm)} руб."
        elif to:
            salary_str = f"до {int(to)} руб."
        else:
            salary_str = "Не указана"

        processed.append({
            "Название": v["name"],
            "Компания": v["employer"],
            "Регион / Город": v["area"],
            "Зарплата": salary_str,
            "Опыт (лет)": v["experience"],
            "Тип занятости": v["employment"],
            "Ссылка": v["alternate_url"],
            "salary_num": frm if frm is not None else to
        })
    return pd.DataFrame(processed)

def plot_bar_chart(data_series, x_label, y_label, horizontal=True, color="#1f77b4", is_int=True):
    df_chart = data_series.reset_index()
    df_chart.columns = ["category", "value"]
    
    num_format = "d" if is_int else ",.0f"
    val_scale = alt.Scale(domainMin=0, nice=True)
    axis_title = x_label if horizontal else y_label
    cat_title = y_label if horizontal else x_label
    
    if is_int:
        val_axis = alt.Axis(title=axis_title, format=num_format, tickMinStep=1)
    else:
        val_axis = alt.Axis(title=axis_title, format=num_format)
        
    cat_axis = alt.Axis(title=cat_title, labelLimit=200)
    
    if horizontal:
        chart = alt.Chart(df_chart).mark_bar(color=color, cornerRadiusEnd=4).encode(
            x=alt.X("value:Q", scale=val_scale, axis=val_axis),
            y=alt.Y("category:N", sort="-x", axis=cat_axis),
            tooltip=[
                alt.Tooltip("category:N", title=y_label),
                alt.Tooltip("value:Q", title=x_label, format=num_format)
            ]
        )
    else:
        chart = alt.Chart(df_chart).mark_bar(color=color, cornerRadiusEnd=4).encode(
            x=alt.X("category:N", sort="-y", axis=cat_axis),
            y=alt.Y("value:Q", scale=val_scale, axis=val_axis),
            tooltip=[
                alt.Tooltip("category:N", title=x_label),
                alt.Tooltip("value:Q", title=y_label, format=num_format)
            ]
        )
        
    return chart.properties(height=320)

# Инициализация состояния сессии
if "raw_data" not in st.session_state:
    st.session_state.raw_data = None
if "last_query" not in st.session_state:
    st.session_state.last_query = search_query

# Кнопка запуска парсинга
if st.sidebar.button("🚀 Собрать вакансии", use_container_width=True):
    with st.spinner("Загрузка данных из единой государственной системы..."):
        st.session_state.raw_data = fetch_vacancies_trudvsem(search_query, limit_vacancies)
        st.session_state.last_query = search_query

# Отображение результатов
if st.session_state.raw_data is not None:
    raw_data = st.session_state.raw_data
    
    if raw_data:
        df = process_data(raw_data, only_with_salary)
        
        if not df.empty:
            st.sidebar.divider()
            st.sidebar.header("📍 Фильтр по региону")
            
            region_counts = df["Регион / Город"].value_counts()
            region_options = ["Все регионы"] + [f"{reg} ({cnt})" for reg, cnt in region_counts.items()]
            selected_option = st.sidebar.selectbox("Выберите регион", region_options)
            
            if selected_option != "Все регионы":
                selected_region = selected_option.rsplit(" (", 1)[0]
                df = df[df["Регион / Город"] == selected_region]

            if sort_order == "По убыванию (сначала дорогие)":
                df = df.sort_values(by="salary_num", ascending=False, na_position='last')
            elif sort_order == "По возрастанию":
                df = df.sort_values(by="salary_num", ascending=True, na_position='last')
            
            # Блок верхних метрик
            st.markdown("### 📊 Аналитические метрики")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Отображено вакансий", len(df))
            col2.metric("Уникальных регионов", df["Регион / Город"].nunique())
            
            df_with_sal = df[df["salary_num"].notna()]
            if not df_with_sal.empty:
                col3.metric("Средняя стартовая ЗП", f"{int(df_with_sal['salary_num'].mean()):,} руб.".replace(",", " "))
            else:
                col3.metric("Средняя стартовая ЗП", "Нет данных")
                
            final_df = df.drop(columns=['salary_num'])
            csv = final_df.to_csv(index=False).encode('utf-8-sig')
            col4.download_button(
                label="📥 Скачать таблицу CSV",
                data=csv,
                file_name=f"vacancies_{st.session_state.last_query}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            # Вкладки для разделения визуализации и таблицы
            tab_charts, tab_table = st.tabs(["📈 Визуализация и графики", "📋 Таблица вакансий"])
            
            with tab_charts:
                chart_col1, chart_col2 = st.columns(2)
                
                with chart_col1:
                    st.subheader("🏙️ Топ-10 регионов по количеству вакансий")
                    city_counts = df["Регион / Город"].value_counts().head(10)
                    st.altair_chart(
                        plot_bar_chart(city_counts, "Количество вакансий", "Регион", horizontal=True),
                        use_container_width=True
                    )
                
                with chart_col2:
                    st.subheader("💰 Топ-10 регионов по средней зарплате (руб.)")
                    if not df_with_sal.empty:
                        city_salary = df_with_sal.groupby("Регион / Город")["salary_num"].mean().round(0).sort_values(ascending=False).head(10)
                        st.altair_chart(
                            plot_bar_chart(city_salary, "Средняя ЗП (руб.)", "Регион", horizontal=True, color="#2e8b57", is_int=False),
                            use_container_width=True
                        )
                    else:
                        st.info("Недостаточно данных о зарплатах для построения графика.")
                
                st.divider()
                chart_col3, chart_col4 = st.columns(2)
                with chart_col3:
                    st.subheader("🕒 Распределение по типу занятости")
                    emp_counts = df["Тип занятости"].value_counts()
                    st.altair_chart(
                        plot_bar_chart(emp_counts, "Тип занятости", "Количество вакансий", horizontal=False, color="#ff7f0e"),
                        use_container_width=True
                    )
                    
                with chart_col4:
                    st.subheader("🏢 Топ работодателей по числу вакансий")
                    top_companies = df["Компания"].value_counts().head(7)
                    st.altair_chart(
                        plot_bar_chart(top_companies, "Количество вакансий", "Компания", horizontal=True, color="#4682b4"),
                        use_container_width=True
                    )

            with tab_table:
                st.dataframe(
                    final_df,
                    column_config={"Ссылка": st.column_config.LinkColumn("Ссылка на вакансию")},
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.warning("Нет вакансий, соответствующих выбранным фильтрам.")
    else:
        st.warning("По вашему запросу ничего не найдено.")

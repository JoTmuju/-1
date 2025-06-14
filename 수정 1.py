import pandas as pd
import streamlit as st
from collections import defaultdict, Counter
import random
import tempfile

st.title("시험 감독 배정 프로그램")

# 사용자 입력
st.sidebar.header("학급 정보 입력")
class_counts = {
    '1학년': st.sidebar.number_input("1학년 반 수", min_value=1, max_value=10, value=5),
    '2학년': st.sidebar.number_input("2학년 반 수", min_value=1, max_value=10, value=5),
    '3학년': st.sidebar.number_input("3학년 반 수", min_value=1, max_value=10, value=5),
}

total_rooms = sum(class_counts.values())
st.sidebar.markdown(f"**총 시험실 수: {total_rooms}개**")

uploaded_file = st.sidebar.file_uploader("교사 목록 및 시간표 파일 업로드 (.xlsx)", type=["xlsx"])
rerun = st.sidebar.button("🔄 다른 조합으로 재배정")

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    df_raw = xls.parse('교사 목록', header=None)

    # 담임 및 전담 교사 정리
    homeroom_raw = df_raw.iloc[:, 1:4].dropna(how='all')
    homeroom_raw.columns = ['학급', '이름', '담당교과']
    homeroom_raw = homeroom_raw.dropna()
    subject_raw = df_raw.iloc[:, 5:7].dropna(how='all')
    subject_raw.columns = ['이름', '담당교과']
    subject_raw = subject_raw.dropna()

    homeroom_raw['담임여부'] = True
    homeroom_raw['담임학년'] = homeroom_raw['학급'].str.extract(r'(\d)학년').astype(float)
    homeroom_raw['담임반'] = homeroom_raw['학급'].str.extract(r'(\d)반').astype(float)
    subject_raw['담임여부'] = False
    subject_raw['담임학년'] = None
    subject_raw['담임반'] = None

    teacher_df = pd.concat([
        homeroom_raw[['이름', '담당교과', '담임여부', '담임학년', '담임반']],
        subject_raw[['이름', '담당교과', '담임여부', '담임학년', '담임반']]
    ], ignore_index=True)

    all_teachers = teacher_df['이름'].tolist()

    # 가상의 시간표 시간대 정의 (예: 1교시~6교시 3일)
    time_slots = [f"{day}일차 {period}교시" for day in range(1, 4) for period in range(1, 7)]

    schedule = defaultdict(lambda: {'정감독': [], '부감독': []})
    total_assignments = Counter()
    role_counts = defaultdict(lambda: {'정감독': 0, '부감독': 0})

    for time in time_slots:
        random.shuffle(all_teachers)
        assigned = set()
        role_slots = {'정감독': total_rooms, '부감독': total_rooms}

        for role in ['정감독', '부감독']:
            for _ in range(role_slots[role]):
                eligible = [c for c in all_teachers if c not in assigned and total_assignments[c] < min(total_assignments.values(), default=0) + 2]
                if not eligible:
                    break
                selected = random.choice(eligible)
                schedule[time][role].append(selected)
                total_assignments[selected] += 1
                role_counts[selected][role] += 1
                assigned.add(selected)

    st.subheader("시험 감독 배정 결과")
    all_results = []
    for time in sorted(schedule.keys()):
        st.markdown(f"### {time}")
        df = pd.DataFrame({
            '시험실': [f"{i+1}반" for i in range(total_rooms)],
            '정감독': schedule[time]['정감독'][:total_rooms],
            '부감독': schedule[time]['부감독'][:total_rooms]
        })
        st.dataframe(df)
        df.insert(0, '시간', time)
        all_results.append(df)

    st.subheader("감독 횟수 요약")
    summary = pd.DataFrame([{ 
        '이름': name, 
        '정감독 횟수': counts['정감독'],
        '부감독 횟수': counts['부감독'],
        '총 감독 횟수': counts['정감독'] + counts['부감독']
    } for name, counts in role_counts.items()])
    st.dataframe(summary.sort_values(by='총 감독 횟수', ascending=False))

    st.subheader("엑셀 다운로드")
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            with pd.ExcelWriter(tmp.name, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False, sheet_name='배정표')
                summary.to_excel(writer, index=False, sheet_name='감독요약')
            with open(tmp.name, "rb") as f:
                st.download_button(label="📥 배정표 엑셀 다운로드", data=f, file_name="감독_배정표.xlsx")

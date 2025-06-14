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
    teacher_df = xls.parse('교사 목록')
    timetable_df = xls.parse('시간표')

    # 교사 정보 분리
    homeroom_teachers = {}
    other_teachers = []
    for _, row in teacher_df.iterrows():
        name = row['이름']
        if pd.isna(row['담임학년']) or pd.isna(row['담임반']):
            other_teachers.append(name)
        else:
            homeroom_teachers[name] = f"{int(row['담임학년'])}-{int(row['담임반'])}"

    all_teachers = list(homeroom_teachers.keys()) + other_teachers
    available_slots = defaultdict(list)

    for _, row in timetable_df.iterrows():
        name = row['이름']
        if name not in all_teachers:
            continue
        for col in timetable_df.columns[1:]:
            if row[col] == '공강':
                available_slots[col].append(name)

    schedule = defaultdict(lambda: {'정감독': [], '부감독': []})
    total_assignments = Counter()
    role_counts = defaultdict(lambda: {'정감독': 0, '부감독': 0})

    for time, candidates in available_slots.items():
        random.shuffle(candidates)
        assigned = set()
        role_slots = {'정감독': total_rooms, '부감독': total_rooms}

        for role in ['정감독', '부감독']:
            for _ in range(role_slots[role]):
                eligible = [c for c in candidates if c not in assigned and total_assignments[c] < min(total_assignments.values(), default=0) + 2]
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

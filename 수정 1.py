import streamlit as st
import pandas as pd
import random
from collections import defaultdict
import tempfile

# ========== 주석: 배정 알고리즘 함수 ==========
def assign_supervisors(
    teacher_df, timetable_df, n_class1, n_class2, n_class3, teacher_exclude
):
    """
    주어진 교사, 시간표 DataFrame과 각종 옵션으로 감독자 배정표/통계를 생성
    """
    homeroom_info = {}
    other_teachers = []
    for _, row in teacher_df.iterrows():
        class_name = row['Unnamed: 1']
        if pd.notna(class_name):
            homeroom_info[class_name.strip()] = {
                '이름': row['담임교사'].strip(),
                '교과목': row['담당 교과목'].strip() if pd.notna(row['담당 교과목']) else ''
            }
        if pd.notna(row['교사']) and pd.notna(row['담당 교과목.1']):
            other_teachers.append({
                '이름': row['교사'].strip(),
                '교과목': row['담당 교과목.1'].strip()
            })
    all_teachers = {t['이름']: t['교과목'] for t in other_teachers}
    for info in homeroom_info.values():
        all_teachers[info['이름']] = info['교과목']

    # 시간표 파싱
    subject_rows = timetable_df.iloc[4:]
    day_columns = [
        '첫째날_1교시', '첫째날_2교시', '첫째날_3교시',
        '둘째날_1교시', '둘째날_2교시', '둘째날_3교시',
        '셋째날_1교시', '셋째날_2교시', '셋째날_3교시'
    ]
    timetable_data = []
    for row in subject_rows.itertuples(index=False):
        grade = str(row[1]).strip()
        if '학년' not in grade:
            continue
        for i, subject in enumerate(row[2:11]):
            if pd.notna(subject):
                timetable_data.append({
                    '학년': grade,
                    '교시': day_columns[i],
                    '과목': str(subject).strip()
                })

    class_counts = {'1학년': n_class1, '2학년': n_class2, '3학년': n_class3}

    # 감독시간표 생성
    schedule = []
    for entry in timetable_data:
        for n in range(1, class_counts[entry['학년']] + 1):
            schedule.append({
                '학년': entry['학년'],
                '반': f"{entry['학년']} {n}반",
                '교시': entry['교시'],
                '과목': entry['과목']
            })

    teacher_assignment_count = defaultdict(int)
    teacher_role_count = defaultdict(lambda: {'정감독': 0, '부감독': 0})
    teacher_used_pairs = set()
    class_supervised = defaultdict(set)
    assignments = []

    all_teacher_list = list(all_teachers.keys())
    total_supervisions = len([s for s in schedule if '자습' not in s['과목']])
    target_regular = total_supervisions // len(all_teacher_list)
    target_assist = total_supervisions // len(all_teacher_list)

    random.shuffle(schedule)  # 배정 결과 랜덤

    for item in schedule:
        반이름 = item['반']
        학년 = item['학년']
        교시 = item['교시']
        과목 = item['과목']
        is_self_study = '자습' in 과목

        excluded_teachers = set()
        if 반이름 in homeroom_info:
            excluded_teachers.add(homeroom_info[반이름]['이름'])
        for name, sub in all_teachers.items():
            if any(s in 과목 for s in sub.split('/')):
                excluded_teachers.add(name)
            # Streamlit에서 받아온 제외 교시
            if (학년, 교시) in teacher_exclude.get(name, []):
                excluded_teachers.add(name)
            if 반이름 in class_supervised[name]:
                excluded_teachers.add(name)

        available_teachers = [t for t in all_teachers if t not in excluded_teachers]
        random.shuffle(available_teachers)

        if is_self_study:
            if available_teachers:
                정감독 = available_teachers[0]
                teacher_assignment_count[정감독] += 1
                teacher_role_count[정감독]['정감독'] += 1
                class_supervised[정감독].add(반이름)
                assignments.append({
                    '학년': 학년, '반': 반이름, '교시': 교시, '과목': 과목,
                    '정감독': 정감독, '부감독': ''
                })
            else:
                assignments.append({
                    '학년': 학년, '반': 반이름, '교시': 교시, '과목': 과목,
                    '정감독': '배정불가', '부감독': ''
                })
            continue

        found = False
        for i in range(len(available_teachers)):
            for j in range(i + 1, len(available_teachers)):
                a, b = available_teachers[i], available_teachers[j]
                if (
                    (a, b) not in teacher_used_pairs and
                    (b, a) not in teacher_used_pairs and
                    teacher_role_count[a]['정감독'] <= target_regular and
                    teacher_role_count[b]['부감독'] <= target_assist
                ):
                    teacher_used_pairs.add((a, b))
                    teacher_assignment_count[a] += 1
                    teacher_assignment_count[b] += 1
                    teacher_role_count[a]['정감독'] += 1
                    teacher_role_count[b]['부감독'] += 1
                    class_supervised[a].add(반이름)
                    class_supervised[b].add(반이름)
                    assignments.append({
                        '학년': 학년, '반': 반이름, '교시': 교시, '과목': 과목,
                        '정감독': a, '부감독': b
                    })
                    found = True
                    break
            if found:
                break
        if not found:
            assignments.append({
                '학년': 학년, '반': 반이름, '교시': 교시, '과목': 과목,
                '정감독': '배정불가', '부감독': '배정불가'
            })

    assignment_df = pd.DataFrame(assignments)
    stats_df = pd.DataFrame([
        {
            '교사': k,
            '정감독 횟수': v['정감독'],
            '부감독 횟수': v['부감독'],
            '총합': v['정감독'] + v['부감독']
        }
        for k, v in teacher_role_count.items()
    ])

    return assignment_df, stats_df


# ========== Streamlit UI ==========
st.title("시험 감독 배정 프로그램")

st.sidebar.header("학급 정보 입력")
n_class1 = st.sidebar.number_input("1학년 반 수", min_value=1, max_value=10, value=5)
n_class2 = st.sidebar.number_input("2학년 반 수", min_value=1, max_value=10, value=5)
n_class3 = st.sidebar.number_input("3학년 반 수", min_value=1, max_value=10, value=4)
uploaded_file = st.sidebar.file_uploader("교사 목록 및 시간표 파일 업로드 (.xlsx)", type=["xlsx"])
rerun = st.sidebar.button("🔄 다른 조합으로 재배정")

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    teacher_df = xls.parse('교사 목록')
    timetable_df = xls.parse('시간표')

    # 교사별 예외 시간 설정 UI
    st.sidebar.header("감독 제외 시간 설정")
    all_teacher_names = list(
        teacher_df['담임교사'].dropna().apply(str).unique()
    ) + list(teacher_df['교사'].dropna().apply(str).unique())
    teacher_exclude = defaultdict(list)
    for name in all_teacher_names:
        with st.sidebar.expander(f"{name} 제외 시간"):
            for g in ['1학년', '2학년', '3학년']:
                selected = st.multiselect(
                    f"{g} 교시(예: 첫째날_1교시, 둘째날_2교시 ...)",
                    [f"{d}_{p}" for d in ['첫째날', '둘째날', '셋째날'] for p in ['1교시', '2교시', '3교시']],
                    key=f"{name}-{g}"
                )
                for p in selected:
                    teacher_exclude[name].append((g, p))

    # 배정 실행
    assignment_df, stats_df = assign_supervisors(
        teacher_df, timetable_df, n_class1, n_class2, n_class3, teacher_exclude
    )
    st.subheader("📋 시험감독 배정표 (미리보기)")
    st.dataframe(assignment_df)
    st.subheader("감독자별 통계")
    st.dataframe(stats_df)

    # 다운로드 버튼
    if st.button("📥 엑셀 파일로 다운로드"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            with pd.ExcelWriter(tmp.name, engine='xlsxwriter') as writer:
                assignment_df.to_excel(writer, sheet_name='감독 배정표', index=False)
                stats_df.to_excel(writer, sheet_name='감독 횟수 요약', index=False)
            st.download_button(
                label="📎 다운로드",
                data=open(tmp.name, 'rb').read(),
                file_name="시험감독_배정표.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

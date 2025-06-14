# assigner.py
import pandas as pd
from collections import defaultdict
import random

def assign_supervisors(teacher_df, schedule_df, n_class1, n_class2, n_class3, teacher_exclude):
    # 교사 담당과목 정리
    teacher_part = teacher_df.iloc[:, [5, 6]].dropna()
    teacher_part.columns = ['이름', '담당과목']
    teacher_list = teacher_part['이름'].tolist()
    subject_map = dict(zip(teacher_part['이름'], teacher_part['담당과목']))

    # 시험 시간표 정리
    exam_schedule = schedule_df.iloc[4:].copy()
    exam_schedule.columns = schedule_df.iloc[3]
    exam_schedule.reset_index(drop=True, inplace=True)
    grades = exam_schedule['학년 \ 교시'].tolist()
    period_subjects = exam_schedule.drop(columns='학년 \ 교시')
    period_subjects.columns = [
        '첫째날_1교시', '첫째날_2교시', '첫째날_3교시',
        '둘째날_1교시', '둘째날_2교시', '둘째날_3교시',
        '셋째날_1교시', '셋째날_2교시', '셋째날_3교시', '여분']
    period_subjects = period_subjects.iloc[:, :-1]  # 여분 제거

    반정보 = {
        '1학년': [f'1-{i+1}' for i in range(n_class1)],
        '2학년': [f'2-{i+1}' for i in range(n_class2)],
        '3학년': [f'3-{i+1}' for i in range(n_class3)],
    }

    schedule_data = []
    for i, grade in enumerate(grades):
        for j, col in enumerate(period_subjects.columns):
            subject = period_subjects.iloc[i, j]
            if pd.notna(subject):
                for 반 in 반정보[grade]:
                    schedule_data.append({
                        '학년': grade,
                        '반': 반,
                        '교시': col,
                        '과목': subject.strip()
                    })

    df = pd.DataFrame(schedule_data)

    teacher_assign_count = {name: 0 for name in teacher_list}
    assigned_pairs = set()
    used_combinations = defaultdict(set)
    teacher_class_history = defaultdict(set)

    results = []
    for (반, 교시), group in df.groupby(['반', '교시']):
        과목들 = group['과목'].unique().tolist()
        자습여부 = all(subj == '자습' for subj in 과목들)

        제외 = set()
        for subj in 과목들:
            제외.update(teacher_part[teacher_part['담당과목'] == subj]['이름'].tolist())
        for t in teacher_list:
            if 교시 in teacher_exclude.get(t, []):
                제외.add(t)
            if 반.startswith(t[0]) and t in teacher_df.iloc[:, 2].tolist():  # 담임 교사 제외
                제외.add(t)
            if 반 in teacher_class_history[t]:
                제외.add(t)

        후보 = [t for t in teacher_list if t not in 제외]
        후보.sort(key=lambda x: teacher_assign_count[x])

        정, 부 = None, None
        for t in 후보:
            if 정 is None:
                정 = t
            elif 부 is None and (정, t) not in assigned_pairs and t != 정:
                부 = t
                break

        teacher_assign_count[정] += 1
        teacher_class_history[정].add(반)
        if not 자습여부 and 부:
            teacher_assign_count[부] += 1
            teacher_class_history[부].add(반)
            assigned_pairs.add((정, 부))
            assigned_pairs.add((부, 정))

        results.append({
            '반': 반,
            '교시': 교시,
            '정감독': 정,
            '부감독': 부 if not 자습여부 else None
        })

    result_df = pd.DataFrame(results)
    count_df = result_df.melt(id_vars=['반', '교시'], value_vars=['정감독', '부감독'],
                              var_name='구분', value_name='교사').dropna()
    stats_df = count_df['교사'].value_counts().reset_index()
    stats_df.columns = ['교사', '총 감독 횟수']

    정감독_counts = result_df['정감독'].value_counts().reset_index()
    정감독_counts.columns = ['교사', '정감독 횟수']
    부감독_counts = result_df['부감독'].value_counts().reset_index()
    부감독_counts.columns = ['교사', '부감독 횟수']

    stats_df = stats_df.merge(정감독_counts, on='교사', how='left')
    stats_df = stats_df.merge(부감독_counts, on='교사', how='left')
    stats_df.fillna(0, inplace=True)
    stats_df[['정감독 횟수', '부감독 횟수']] = stats_df[['정감독 횟수', '부감독 횟수']].astype(int)

    return result_df, stats_df

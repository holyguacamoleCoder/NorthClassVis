import numpy as np
import pandas as pd

def generate_parallel_view_data(num_students=1000, num_titles=50, num_knowledges=10):
    # Generate student IDs and title IDs
    student_ids = [f'student{i}' for i in range(num_students)]
    title_ids = [i for i in range(1, num_titles + 1)]
    knowledge_ids = [f'knowledge{j}' for j in range(num_knowledges)]

    # Generate SubmitRecord data
    submit_records = []
    for student_id in student_ids:
        for _ in range(np.random.randint(1, 100)):  # Each student submits between 1 to 9 titles
            title_id = np.random.choice(title_ids)
            score = np.random.randint(1, 100)
            timeconsume = np.random.uniform(1, 60)
            memory = np.random.uniform(1, 1024)
            state = np.random.choice(['Absolutely_Correct', 'Incorrect'])
            method = np.random.choice(['methodA', 'methodB', 'methodC'])
            timestamp = pd.Timestamp.now() - pd.Timedelta(days=np.random.randint(0, 365))
            
            submit_records.append({
                'index': len(submit_records),
                'class': f'class{np.random.randint(1, 11)}',
                'time': timestamp,
                'state': state,
                'score': score,
                'title_ID': title_id,
                'method': method,
                'memory': memory,
                'timeconsume': timeconsume,
                'student_ID': student_id
            })

    submit_record_df = pd.DataFrame(submit_records)

    # Generate StuInfo data
    stu_info = []
    for student_id in student_ids:
        sex = np.random.choice(['Male', 'Female'])
        age = np.random.randint(18, 30)
        major = np.random.choice(['Computer Science', 'Mathematics', 'Physics', 'Chemistry', 'Biology'])
        
        stu_info.append({
            'index': student_id,
            'student_ID': student_id,
            'sex': sex,
            'age': age,
            'major': major
        })

    stu_info_df = pd.DataFrame(stu_info)

    # Generate TitleInfo data
    title_info = []
    for title_id in title_ids:
        score = np.random.randint(1, 100)
        knowledge = np.random.choice(knowledge_ids)
        sub_knowledge = np.random.choice([f'sub_knowledge{k}' for k in range(5)])
        
        title_info.append({
            'index': title_id,
            'title_ID': title_id,
            'score': score,
            'knowledge': knowledge,
            'sub_knowledge': sub_knowledge
        })

    title_info_df = pd.DataFrame(title_info)

    return submit_record_df, stu_info_df, title_info_df
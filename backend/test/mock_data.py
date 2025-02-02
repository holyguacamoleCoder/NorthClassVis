import numpy as np
import pandas as pd

def generate_mock_data(num_students=1000, num_knowledges=10):
    student_ids = [f'student{i}' for i in range(num_students)]
    knowledge_ids = [f'knowledge{j}' for j in range(num_knowledges)]

    data = []
    for student_id in student_ids:
        for knowledge_id in knowledge_ids:
            score = np.random.randint(1, 100)
            timeconsume = np.random.uniform(1, 60)
            memory = np.random.uniform(1, 1024)
            state = np.random.choice(['Absolutely_Correct', 'Incorrect'])
            title_id = np.random.randint(1, 10)
            timestamp = pd.Timestamp.now()
            
            data.append({
                'student_ID': student_id,
                'knowledge': knowledge_id,
                'score': score,
                'timeconsume': timeconsume,
                'memory': memory,
                'state': state,
                'title_ID': title_id,
                'time': timestamp
            })
    
    return pd.DataFrame(data)
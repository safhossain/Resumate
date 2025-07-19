import os
import docx

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
template_file_path = os.path.join(SCRIPT_DIR, '../templates/resume/BASE_RESUME_TEMPL.docx')


doc = docx.Document(template_file_path)
paras = doc.paragraphs

# first = paras[1]
# #print(first.text)

# text=''

# for run_id, run in enumerate(first.runs):
#     text += run.text

# first.runs[0].text = text

# for run_id, run in enumerate(first.runs):
#     if run_id !=0:
#         run._element.getparent().remove(run._element)

# for run_id, run in enumerate(first.runs):
#     print(f'run_{run_id}: {run}:{run.text}')

def normalize_runs():
    all_left_braces = []
    all_right_braces = []

    for para_id, para in enumerate(paras):
        for run_id, run in enumerate(para.runs):
            '''
            possibilities:
            '{{ ... }}'                             : 1 run; no trim req (heaven, optimal happy path)
            '{{ ...' -> '}}' or '{{' -> '... }}'    : 2 runs; no trim req
            '{{' -> '...' -> '}}'                   : 3 runs; no trim req

            complicated:
            '... {' '{' -> '... }} ...'
            '''
            rt = run.text

            # Left / Right Braces in same Run instance
            double_lb_same_run = [i for i in range(len(rt)) if rt.startswith("{{", i)]
            double_rb_same_run = [i for i in range(len(rt)) if rt.startswith("}}", i)]
            
            for lb in double_lb_same_run:
                lb1 = (para_id, run_id, lb)
                lb2 = (para_id, run_id, (lb+1))
                all_left_braces.append(lb1)
                all_left_braces.append(lb2)
            
            for rb in double_rb_same_run:
                rb1 = (para_id, run_id, rb)
                rb2 = (para_id, run_id, (rb+1))
                all_right_braces.append(rb1)
                all_right_braces.append(rb2)            

            # Left / Right Braces in different Run instances 
            # EX: Run_1: "hello {"; Run_2: "{ NAME }}"
            # EX: Run_1: "hello {{"; Run_2: "NAME }"; Run_3: "}"
            # EX: "hello", "{", "{", " NAME ", "}", "}"
    
    
    print(f'Left Braces: {all_left_braces}')
    print(f'Right Braces: {all_right_braces}')
            


            
normalize_runs()            

# test = ["hello {{ NAME }} my name is {", "{ OTHER NAME }}."]
# for sub in test:
#     braces = [i for i, c in enumerate(sub) if c == '{']

#     def split_on_exact_consecutive_pairs(arr):
#         result = []
#         for i in range(1, len(arr)):
#             if arr[i] == arr[i - 1] + 1:                
#                 if (i + 1 == len(arr) or arr[i + 1] != arr[i] + 1) and (i - 2 < 0 or arr[i - 2] != arr[i - 1] - 1):
#                     result.append([arr[i - 1], arr[i]])
#         return result if result else None

#     if braces:
#         print(split_on_exact_consecutive_pairs(braces))


#doc.save(template_file_path)
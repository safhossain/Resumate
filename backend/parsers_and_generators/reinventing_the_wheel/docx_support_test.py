import os
import docx

# For lower level XML modification:
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.run import Run
from lxml import etree

'''
Requirements:
1. Be able to separate all special tokens (and their initial+ending delimeters) and their inner content into separate run instances
2. Be able to add new special tokens as a function
3. When modifying ANY text, has to keep the same style as it previously did. any new run instance should keep the same style as the run before it
4. 
'''
   
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
template_file_path = os.path.join(SCRIPT_DIR, '../templates/resume/BASE_RESUME_TEMPL_2.docx')

doc = docx.Document(template_file_path)
paras = doc.paragraphs

def combine_sister_delimiters(r1_end, r2_start):
    global paras
    for p_id, p in enumerate(paras):
        for run_id, run in enumerate(p.runs):
            rt = run.text
            r2 = None
            
            if (run_id + 1) < len(p.runs): # check if another run exists beyond current run
                r2 = p.runs[run_id+1]
                    
            if r2 and rt.endswith(r1_end) and r2.text.startswith(r2_start):
                run.add_text(r2_start)
                beyond = r2.text.replace(r2_start, "")
                r2.clear()
                r2.add_text(beyond)

def insert_run_after(run, text=None, style=None): # ChatGPT-Written
    """
    Insert a new Run into the paragraph immediately after `run`.
    - text:       the .text for the new run (None for empty)
    - style:      a character-style name (None for default)
    Returns the new docx.text.run.Run object.
    """
    # 1) Build the raw <w:r> element
    new_r = OxmlElement('w:r')
    # 1a) optional style
    if style is not None:
        rPr = OxmlElement('w:rPr')
        rStyle = OxmlElement('w:rStyle')
        rStyle.set(qn('w:val'), style)
        rPr.append(rStyle)
        new_r.append(rPr)
    # 1b) optional text
    if text is not None:
        t = OxmlElement('w:t')
        # preserve spaces if needed
        if text.strip() != text:
            t.set(qn('xml:space'), 'preserve')
        t.text = text
        new_r.append(t)

    # 2) Splice it into the XML right after the existing run
    run._element.addnext(new_r)

    # 3) Wrap it back as a python-docx Run (parent is the same)
    return Run(new_r, run._parent)

opening_delims = ['{{', '{%%']
closing_delims = ['}}', '%%}']

def string_test_from_string_list(text: str, candidates: list[str], mode:str):
    if mode not in ("startswith", "contains", "endswith"):
        raise ValueError(f"mode != 'startswith', 'contains', 'endswith'; got {mode}")
    for item in candidates:
        if mode == "startswith" and text.startswith(item):
            return item
        if mode == "contains"   and item in text:
            return item
        if mode == "endswith"   and text.endswith(item):
            return item
    return False

def insert_run_breaks():
    global paras, opening_delims, closing_delims
    for p_id, p in enumerate(paras):
        p_runs = p.runs
        for run_id, c_run in enumerate(p_runs):
            crt:str     = c_run.text
            sub:str     = ""
            pointer:int = 0
            
            while (pointer < len(p_runs[run_id].text)):
                sub += crt[pointer]
                contained_opener = string_test_from_string_list(sub, opening_delims, "contains")
                contained_closer = string_test_from_string_list(sub, closing_delims, "contains")

                if contained_opener:
                    '''
                    ['a{{x}}b{{', 'y}}c{{z}}', 'd']
                    ['a', '{{x}}b{{' 'y}}c{{z}}', 'd']            
                    '''
                    before = sub.replace(contained_opener, "")
                    if (before == ""):
                        sub = ""
                        pointer += 1
                        continue
                    
                    index_to_break = (pointer+1) - len(contained_opener)
                    #p_runs.insert(run_id+1, rt[index_to_break:])
                    insert_run_after(c_run, crt[index_to_break:]) # hopefully, executing this statement results in p_runs being updated immediately, so that the for-loop logic works
                    #p_runs[run_id] = before
                    c_run.clear()
                    c_run.add_text(before)

                if contained_closer:
                    '''
                    ['a', '{{x}}b{{' 'y}}c{{z}}', 'd']
                    ['a', '{{x}}', 'b{{' 'y}}c{{z}}', 'd']
                    '''
                    index_to_break = pointer+1
                    beyond = crt[index_to_break:]
                    #p_runs.insert(run_id+1, beyond)
                    insert_run_after(c_run, beyond)
                    #p_runs[run_id] = rt[0:index_to_break]
                    c_run.clear()
                    c_run.add_text(crt[0:index_to_break])

                pointer += 1
        # for run_id, c_run in enumerate(p_runs):
        #     if c_run == "":
        #         p_runs.pop(run_id)

def marriage_proposal():
    '''
    purpose: combine all run instances between a run instance
    with an opening delim up to and including run instance
    with a closing delim
    '''
    global paras, opening_delims, closing_delims
    for p_id, p in enumerate(paras):
        p_runs = p.runs        
        for run_id, c_run in enumerate(p_runs):
            crt:str = c_run.text
            opener = string_test_from_string_list(crt, opening_delims, "startswith")            
            if opener:
                closer = string_test_from_string_list(crt, closing_delims, "endswith")
                run_id_temp:int = run_id + 1
                while (not closer and run_id_temp < len(p_runs)):
                    crt_next = p_runs[run_id_temp].text
                    closer = string_test_from_string_list(crt_next, closing_delims, "endswith")
                    c_run.add_text(crt_next)
                    p_runs[run_id_temp].clear()
                    run_id_temp += 1

delimiter_combinations = [("{", "{"), ("}", "}"), ("{%", "%"), ("{", "%%"), ("%", "%}"), ("%%", "}")]
for combination in delimiter_combinations:
    combine_sister_delimiters(combination[0], combination[1])
insert_run_breaks()
marriage_proposal()

for p_id, p in enumerate(paras):
    for run_id, run in enumerate(p.runs):
        # xml = etree.tostring(run._element, encoding='unicode', method='xml')        
        # print(f'({p_id},{run_id}) XML:\n{xml}\n')
        print(f'({p_id}, {run_id}); {run}: {run.text.strip()}')
    print("---")

try:
    doc.save(template_file_path)
except Exception as e:
    print("Save failed:", e)
else:
    print("Save (probably) succeeded")

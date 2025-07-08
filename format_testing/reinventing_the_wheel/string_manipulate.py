def string_match_from_string_list(run_str: str, ls: list):
    for item in ls:
        if (run_str.find(item) != -1):
            return item
    return None

runs1 = ['a{{x}}b{{', 'y}}c{{z}}', 'd']

opening_delims = ['{{', '{%%']
closing_delims = ['}}', '%%}']

def insert_run_breaks(runs:list):
    global opening_delims, closing_delims
    for run_id, run in enumerate(runs):
        sub:str = ""
        pointer = 0
        while (pointer < len(runs[run_id])):
            sub += run[pointer]            
            contained_opener = string_match_from_string_list(sub, opening_delims)
            contained_closer = string_match_from_string_list(sub, closing_delims)
            if contained_opener:
                '''
                ['a{{x}}b{{', 'y}}c{{z}}', 'd']
                ['a', '{{x}}b{{' 'y}}c{{z}}', 'd']            
                '''
                before = sub.replace(contained_opener, "")
                if (before == ""):
                    sub = ""
                    pointer+=1
                    continue
                
                index_to_break = (pointer+1) - len(contained_opener)

                runs.insert(run_id+1, run[index_to_break:])
                runs[run_id] = before
            if contained_closer:
                '''            
                ['a', '{{x}}b{{' 'y}}c{{z}}', 'd']
                ['a', '{{x}}', 'b{{' 'y}}c{{z}}', 'd']
                '''
                index_to_break = pointer+1
                beyond = run[index_to_break:]
                runs.insert(run_id+1, beyond)
                runs[run_id] = run[0:index_to_break]

            pointer+=1
    for run_id, run in enumerate(runs):
        if run=='':
            runs.pop(run_id)

def test_cases():
    cases = {
        "original":                     ['a{{x}}b{{', 'y}}c{{z}}', 'd'],  
        "runs1_no_delims":              ['plain text without any markers'],
        "runs2_start_opener":           ['{{START only opener here'],
        "runs3_end_closer":             ['some text only closer here}}'],
        "runs4_back_to_back":           ['{{}}'],
        "runs5_single_block":           ['prefix {{middle}} suffix'],
        "runs6_two_blocks":             ['a{{x}}b{{y}}c'],
        "runs7_percent_style":          ['open {%%percent%%} close'],
        "runs8_nested":                 ['start {{a{{b}}c}} end'],
        "runs9_delim_at_run_edge":      ['foo', 'bar{{', 'baz'],
        "runs10_empty_and_only":        ['', '{{', '}}', '{%%', '%%}'],
    }

    for name, runs in cases.items():
        print(f"\n=== {name} ===")
        print("Before:", runs)
        insert_run_breaks(runs)
        print(" After:", runs)

test_cases()
import pathlib
import json
import pandas as pd
from uuid import uuid4
from flask import Flask
from flask import request
from flask import send_from_directory
from wikifier.wikifier import Wikifier
import requests
import time

app = Flask(__name__)

wikifier = Wikifier()
config = json.load(open('wikifier/config.json'))




@app.route('/rec', methods=['POST','GET'])
def rec():
   
    #print(request.headers)
    #print(request.data)
    #print(request.form)
    #print(request.args)
    #print(request.url)
    #print(request.__dict__)
    #print(request.referrer)
    #if flask.request.method == 'POST':
    #    print(flask.request)


    #deal with callback requests for general info

    query = request.form.get('queries')

    if query == None:
         query = request.args.get('queries')
    
    if query == None:
        callback = request.args.get('callback', False)
        if callback:
            content = str(callback) + '(' + str({
           "name" : "Table-Linker Reconciliation for OpenRefine (en)",
           "identifierSpace" : "http://www.wikidata.org/entity/",
           "schemaSpace" : "http://www.wikidata.org/prop/direct/",
           "view" : {
           "url" : "https://www.wikidata.org/wiki/{{id}}"
           }}) + ')'
            return content
        else:
            return {
           "name" : "Wikidata Reconciliation for OpenRefine (en)",
           "identifierSpace" : "http://www.wikidata.org/entity/",
           "schemaSpace" : "http://www.wikidata.org/prop/direct/",
           "view" : {
           "url" : "https://www.wikidata.org/wiki/{{id}}"
           }}
    #deal with post/get queries         
    else: 
        k =3 
        query = json.loads(query)

        df = pd.DataFrame.from_dict(query, orient='index')


        #df.to_csv('./test.csv')

        label = []
        for key in query.keys():
            label.append(key)
        df = df.reset_index(drop = True)
        columns = 'query'

        print(df)

        if (len(df)) > 0 and 'properties' in df.columns:
            for ele in (df['properties'][0]):
                df[ele['pid']] = ''
        
            for i in range(0, len(df)):
                ele = (df['properties'][i])
                for col in ele:
                    df[col['pid']][i] = col['v']
            if 'type' in df.columns:
                df = df.drop('type', 1)
            df = df.drop('properties', 1)

            if 'type_strict' in df.columns:
                df = df.drop('type_strict', 1)


        _uuid_hex = uuid4().hex

        _path = 'user_files/{}_{}'.format(columns, _uuid_hex)
        pathlib.Path(_path).mkdir(parents=True, exist_ok=True)

        wikifier.wikify(df, columns, output_path=_path, debug=True, k=k,
                                      colorized_output='test1.csv')

        df = pd.read_excel(_path + '/colorized.xlsx')


        output = {}
        for ele in label:
            output[ele] = {'result' : []}
    
        for i in range(0, len(df)):
            output[label[df['row'][i]]]['result'].append({
                "id" : df['kg_id'][i],
                "name" : df['kg_labels'][i],
                "type" : [{"id":"/qnode","name":"Qnode"}],
                "score" : df['siamese_prediction'][i],
                "match" : (float(df['siamese_prediction'][i])> 0.95 and int(df['rank'][i]) == 1)
              })
        
        callback = request.args.get('callback', False)
        if callback:
            print(str(callback) + '(' + str(output) + ')')
            return str(callback) + '(' + str(output) + ')'
        else:
            print(output)
            return json.dumps(output)


@app.route('/')
def wikidata_wikifier():
    return "Wikidata Wikifier"


@app.route('/wikify', methods=['POST'])
def wikify():
    columns = request.args.get('columns', None)

    k = int(request.args.get('k', 1))
    colorized_output = request.args.get('colorized', 'false').lower() == 'true'
    nih = request.args.get('nih', 'false').lower() == 'true'
    tsv = request.args.get('tsv', 'fasle').lower() == 'true'

    df = pd.read_csv(request.files['file'], dtype=object) if not tsv else pd.read_csv(request.files['file'],
                                                                                      dtype=object, sep='\t')

    df.fillna('', inplace=True)
    _uuid_hex = uuid4().hex

    _path = 'user_files/{}_{}'.format(columns, _uuid_hex)
    pathlib.Path(_path).mkdir(parents=True, exist_ok=True)

    if nih:
        # this is the NIH case, the output is colorized excel, but we want to return cases where final score
        # is greater that precision_threshold
        output_file = wikifier.wikify(df, columns, output_path=_path, debug=True, k=k,
                                      colorized_output=False,
                                      high_precision=nih)
        odf = pd.read_csv(f'{_path}/{output_file}')
        data = odf.copy()
        _columns = columns.split(",")
        for c in _columns:
            data.loc[data[f'{c}_score'] < 0.9, f'{c}_kg_id'] = 'NIL'
            data.loc[data[f'{c}_score'] < 0.9, f'{c}_score'] = 0

        data.to_csv(f'{_path}/output_high_precision.csv', index=False)
        return send_from_directory(_path, 'output_high_precision.csv')
    else:
        output_file = wikifier.wikify(df, columns, output_path=_path, debug=True, k=k,
                                      colorized_output=colorized_output)
        return send_from_directory(_path, output_file)


if __name__ == '__main__':
    app.run(threaded=True, host=config['host'], port=config['port'])

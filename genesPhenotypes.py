import requests
import csv
import os
from tempfile import NamedTemporaryFile
import getopt, sys


# List of URLs used to find relevant information from IDR
INDEX_PAGE = "https://idr.openmicroscopy.org/webclient/?experimenter=-1"
URL = "https://idr.openmicroscopy.org/mapr/api/{key}/?value={value}&case_sensitive=false&orphaned=true"
SCREENS_PROJECTS_URL = "https://idr.openmicroscopy.org/mapr/api/{key}/?value={value}"
PLATES_URL = "https://idr.openmicroscopy.org/mapr/api/{key}/plates/?value={value}&id={screen_id}"
DATASETS_URL = "https://idr.openmicroscopy.org/mapr/api/{key}/datasets/?value={value}&id={project_id}"
IMAGES_URL = "https://idr.openmicroscopy.org/mapr/api/{key}/images/?value={value}&node={parent_type}&id={parent_id}"
ATTRIBUTES_URL = "https://idr.openmicroscopy.org/webclient/api/annotations/?type=map&image={image_id}"

TYPE = "gene"
KEYS = {"phenotype":
    ("Phenotype",
     "Phenotype Term Name",
     "Phenotype Term Accession",
     "Phenotype Term Accession URL")
}


def parse_annotation(writer, json_data, name, data_type, gene_value, organism=None):
    '''
    Find the phenotype information if any associated to the gene and linked to the images
    '''
    screen_name = "-"
    plate_name = "-"
    project_name = "-"
    dataset_name = "-"
    if data_type == 'datasets':
        project_name = name
    else:
        screen_name = name
     
    for p in json_data[data_type]:
        parent_id = p['id']
        if data_type == 'datasets':
            dataset_name = p['name']
        else:
            plate_name = p['name']
        qs3 = {'key': TYPE, 'value': gene_value,
                'parent_type': data_type[:-1], 'parent_id': parent_id}
        url3 = IMAGES_URL.format(**qs3)
        for i in session.get(url3).json()['images']:

            image_id = i['id']
            url4 = ATTRIBUTES_URL.format(**{'image_id': image_id})
            for a in session.get(url4).json()['annotations']:
                ontologies = []  # for ontology terms for a phenotype
                row = {}
                for v in a['values']:
                    if str(v[0]) in KEYS['phenotype']:
                        if str(v[0]) in ['Phenotype']:  # has phenotype
                            row[str(v[0])] = v[1]  # so create row

                        # if there are ontology mappings for the
                        # phenotype, add them to the ontologies list
                        ontList = ['Phenotype Term Name',
                                   'Phenotype Term Accession',
                                   'Phenotype Term Accession URL']

                        if str(v[0]) in ontList:
                            ontologies.extend([str(v[0]), str(v[1])])
                    if row:
                        if (len(ontologies) > 0):  # 1+ ontology mapping
                            row.update({'Gene': gene_value,
                                        'Screen': screen_name,
                                        'Plate': plate_name,
                                        'Image': image_id,
                                        'Project' : project_name,
                                        'Dataset': dataset_name})
                            # we have the start of a row now
                            # but we want to print out as many rows
                            # as there are ontology mappings
                            # so if there is mapping to 1 ontology term
                            # print 1 row, if there are 2 ontology terms
                            # print 2 rows etc
                            numberOfRows = len(ontologies)/6
                            # this is 3 pairs of ontology values per
                            # mapping, add the ontology mappings and print
                            n = 1
                            while (n <= numberOfRows):
                                row.update({ontologies[0]: ontologies[1],
                                            ontologies[2]: ontologies[3],
                                            ontologies[4]: ontologies[5]})
                                # remove that set of ontology mappings
                                ontologies = ontologies[6:]
                                writer.writerow(row)
                                n = n + 1

def get_genes_and_phenotypes(organism=None):
    '''
    Find the phenotype information linked to the images.
    The results are saved in CSV file in the home directory.
    '''
    home = os.path.expanduser("~")
    csvfile = NamedTemporaryFile("w", delete=False, newline='', dir=home, suffix=".csv")
    try:
        fieldnames = [
            'Gene', 'Screen', 'Plate', 'Project', 'Dataset', 'Image',
            'Phenotype', 'Phenotype Term Name', 'Phenotype Term Accession',
            'Phenotype Term Accession URL']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        new_genes = []
        for g in genes:
            qs1 = {'key': TYPE, 'value': g}
            url1 = URL.format(**qs1)
            json = session.get(url1).json()
            for m in json['maps']: 
                new_genes.append(m['id'])

        for gene in new_genes:
            print(gene)
            qs1 = {'key': TYPE, 'value': gene}
            url1 = URL.format(**qs1)
            json = session.get(url1).json()
            for m in json['maps']:
                qs2 = {'key': TYPE, 'value': gene, 'compound_id': m['id']}
                url2 = SCREENS_PROJECTS_URL.format(**qs2)
                json = session.get(url2).json()
                for s in json['screens']:
                    if s['extra']['value'] is not None:
                        gene = s['extra']['value']
                    qs3 = {'key': TYPE, 'value': gene, 'screen_id': s['id']}
                    url3 = PLATES_URL.format(**qs3)
                    parse_annotation(writer, session.get(url3).json(), s['name'], 'plates', gene, organism)
                for p in json['projects']:
                    if s['extra']['value'] is not None:
                        gene = s['extra']['value']
                    qs3 = {'key': TYPE, 'value': gene, 'project_id': p['id']}
                    url3 = DATASETS_URL.format(**qs3)
                    parse_annotation(writer, session.get(url3).json(), p['name'], 'datasets', gene, organism)
    finally:
        csvfile.close()

if __name__ == "__main__":

    organism = None
    input_file = None
    try:
        arguments_list = sys.argv[1:]
        options = "hof:"
        long_options = ["Help", "Organism", "File"]

        arguments, values = getopt.getopt(arguments_list, options, long_options)
     
        # checking each argument
        for current_argument, current_value in arguments:
 
            if current_argument in ("-h", "--Help"):
                print("Specify organism using either -o or --organism, the CSV file with list of genes with -f or --file")
            elif current_argument in ("-o", "--organism"):
                organism = current_value
            elif current_argument in ("-f", "--file"):
                input_file = current_value
    except getopt.error as err:
    # output error, and return with an error code
        print(str(err))
    print(input_file)
    if input_file is None:
        input_file = "genes_PG.csv"
    with open(input_file, newline='') as f:
        reader = csv.reader(f)
        value = list(reader)

    genes = value[0]
    print(genes)
    with requests.Session() as session:
        request = requests.Request('GET', INDEX_PAGE)
        prepped = session.prepare_request(request)
        response = session.send(prepped)
        if response.status_code != 200:
            response.raise_for_status()
        get_genes_and_phenotypes(organism)
    
    print("done")

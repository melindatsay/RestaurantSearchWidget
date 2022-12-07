import metapy
from finder import Finder
from const import SEARCH_RESULT_COUNT, API_KEY, CITIES, SEARCH_TERMS
import requests


def init_finder(location):
    '''Init Finder class as fndr object. Delete existing index file if 
    the file already exists. Call make_inverted_index() from MeTA 
    toolkit to generate inverted indexes.'''
    fndr = Finder('config.toml', SEARCH_RESULT_COUNT, location)
    fndr.cleaning_existing_index()
    fndr.make_inverted_index()
    fndr.print_index_stats()
    return fndr


def get_restaurant_biz_id_from_yelp_with_term(city_name, term, limit=SEARCH_RESULT_COUNT):
    '''Get a list of 50 resturant business ids in the given city and 
    search term from yelp api endpoint with the following parameters, 
    term as term parameter, city_name as location parameter, limit as 
    limit parameter, "Restaurants" as category parameter and offset as 
    offset parameter.
    '''
    offset = 0
    headers = {
        'Authorization': 'Bearer %s' % API_KEY,
    }
    search_api_url = 'https://api.yelp.com/v3/businesses/search'
    yelp_restaurant_biz_id_with_term = []
    yelp_restaurant_biz_name_with_term = []
    parameters = {
        'term': term,
        'location': city_name,
        'limit': limit,
        'category': 'Restaurants',
        'offset': offset
    }

    response = requests.get(
        search_api_url, headers=headers, params=parameters)
    response.raise_for_status()
    yelp_biz_json = response.json()

    for biz in yelp_biz_json["businesses"]:
        yelp_restaurant_biz_id_with_term.append(biz['id'])
    for biz in yelp_biz_json["businesses"]:
        yelp_restaurant_biz_name_with_term.append(biz['name'])
    return yelp_restaurant_biz_id_with_term


def calculate_precision():
    '''Get a list of 50 resturant business ids in the given city and 
    search term from yelp api endpoint as "Correct 
    Relevant Results".
    
    Generate each city's top 50 relevant restaurants results with 
    given search term from find_restaurants(query_str) in finder.py by 
    using each city's review texts corpus file prepared by 
    dataset_eval.py. 
    
    Compare results generated by restaurant_finder ranking 
    algorithm and "Correct Relevant Results" from yelp api endpoint to
    calculate the precision. 

    Calculate the mean of 5 search term precision for each city.
    '''
    cities = CITIES
    search_terms = SEARCH_TERMS
    limit = SEARCH_RESULT_COUNT 
    precisions = {}
    for city_name in cities:
        print(city_name, end=':')
        finder = init_finder(location=city_name)
        precision = []
        for search_term in search_terms:
            print('Getting {} restaurant biz ids when searching {} in {} from yelp api endpoint...'.format(limit, search_term, city_name))
            yelp_top_results = get_restaurant_biz_id_from_yelp_with_term(
                city_name, search_term, limit)
            print('Yelp has {} results and {} distinct results'.format(len(yelp_top_results), len(set(yelp_top_results))))
            results = finder.find_restaurants(search_term)
            ranked_biz_list = [biz['business_id'] for biz in results]
            print('App has {} results and {} distinct results'.format(len(ranked_biz_list), len(set(ranked_biz_list))))
            results_in_yelp = list(filter(
                lambda biz: biz['business_id'] in yelp_top_results, results))
            print('Comparing results...')
            precision_result = len(results_in_yelp)/limit
            print('Precision is {:.2f} in {} when searching {}'.format(precision_result, city_name, search_term))
            precision.append(precision_result)
        precisions[city_name] = precision
    print('Mean of 5 search terms precision in each city:')
    for city_name, precision in precisions.items():
        print('{:<15}: {:.2f}'.format(city_name, sum(precision)/len(precision)))


if __name__ == '__main__':
    metapy.log_to_stderr()
    calculate_precision()
    
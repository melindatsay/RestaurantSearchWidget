import requests
import orjson
import argparse
import sys
from const import *
from switches import *


def get_restaurant_biz_id_from_yelp(city_name, limit=50):
    '''Get a list of 1,000 resturant business ids in the given city 
    from yelp api endpoint with the following parameters, city_name as 
    location parameter, limit as limit parameter, "Restaurants" as 
    category parameter and offset as offset parameter.
    '''
    offset = 0
    headers = {
        'Authorization': 'Bearer %s' % API_KEY,
    }
    search_api_url = 'https://api.yelp.com/v3/businesses/search'
    yelp_restaurant_biz_id = []
    for i in range(20):
        parameters = {
            'location': city_name,
            'limit': limit,
            'category': 'Restaurants',
            'offset': offset
        }

        response = requests.get(
            search_api_url, headers=headers, params=parameters)
        response.raise_for_status()
        yelp_biz_json = response.json()

        for biz in yelp_biz_json['businesses']:
            yelp_restaurant_biz_id.append(biz['id'])
        print(len(yelp_restaurant_biz_id))
        offset += 50
    return yelp_restaurant_biz_id


def get_restaurants(dataset_path, city_name):
    '''Get a list of restaurants and a dictionary of restaurant_idx, 
    where key is restaurant's business id and value is assigned index.
    '''
    restaurant_cat_list = ['restaurants']
    restaurants = []
    restaurant_idx = {}

    with open(dataset_path / (FULL_DATASET_FILE_PREFIX + 'business.json'), 'r', encoding='utf8') as r:
        for line in r:
            biz = orjson.loads(line)
            if biz['categories'] is None:
                continue
            if biz['city'] != city_name:
                continue
            biz_cats = [x.strip() for x in biz['categories'].split(',')]
            for category in biz_cats:
                if category.lower() in restaurant_cat_list:
                    restaurants.append(biz)
                    biz_id = biz['business_id']
                    if biz_id in restaurant_idx:
                        raise KeyError(f'Business id, {biz_id}, already exists in the restaurant index dict. \
                                       Business id should be unique in the business dataset.')
                    restaurant_idx[biz_id] = len(restaurants) - 1
                    break
    return restaurants, restaurant_idx


def get_overlap_restaurants(dataset_path, city_name, yelp_restaurant_biz_id):
    '''Get a list of overlapping restaurants and a dictionary of overlapping 
    restaurant_idx in the given city between yelp academic dataset and 
    the list of 1,000 resturant business ids returned by function 
    get_restaurant_biz_id_from_yelp(city_name, limit=50)
    '''
    restaurants, _ = get_restaurants(dataset_path, city_name)
    overlap = []
    overlap_idx = {}
    for r in restaurants:
        biz_id = r['business_id']
        if biz_id in yelp_restaurant_biz_id:
            overlap.append(r)
            overlap_idx[biz_id] = len(overlap) - 1
    print('There are {} overlapping restaurants.'.format(len(overlap)))
    return overlap, overlap_idx


def expand_review_with_categories(restaurant, review_txt):
    '''Add review's corresponding restaurant business category to 
    review text. This feature can be turned on and off in switches.py. 
    The default setting is on.
    '''
    expanded_review = ''
    expanded_review += review_txt
    categories = restaurant['categories']
    if categories is None or categories.strip() == '':
        return expanded_review
    for c in restaurant['categories'].split(','):
        c = c.lower().strip()
        category_words = c.split(' ')
        for word in category_words:
            word = word.strip()
            if word == '&' or word == 'and' or 'restaurant' in word:
                continue
            # if category word already exists in review then not adding it again to the review
            # otherwise I think duplicate word can increase emphasis on that word
            if word not in review_txt:
                expanded_review = word + ' ' + expanded_review
    return expanded_review


def get_reviews_per_biz(dataset_path, restaurant_idx, review_limit_per_biz):
    '''Get a dictionary of reviews, where each key is restaurant's business 
    id and value is a list of that restaurant's first 100 reviews with 5000 
    characters limitation for each review if available
    '''
    biz_ids = set(restaurant_idx.keys())
    biz_review_count = {}
    reviews = {}

    for i in biz_ids:
        biz_review_count[i] = 0

    with open(dataset_path / (FULL_DATASET_FILE_PREFIX + 'review.json'), 'r', encoding='utf8') as r:
        for line in r:
            review = orjson.loads(line)
            biz_id = review['business_id']
            if biz_id in biz_ids:
                biz_review_count[biz_id] += 1
                if biz_review_count[biz_id] > review_limit_per_biz:
                    continue

                review = {
                    'business_id': review['business_id'],
                    'stars': review['stars'],
                    'text': review['text']
                }

                if biz_id not in reviews:
                    reviews[biz_id] = []
                reviews[biz_id].append(review)

    return reviews


def get_reviews(dataset_path, restaurants, restaurant_idx, review_limit_per_biz, review_len_limit):
    '''Get a dictionary of reviews returned by 
    get_reviews_per_biz(dataset_path, restaurant_idx, review_limit_per_biz)
    
    Get a list of final_review_txts by combining all the review texts in 
    all values from the above dictionary.
    
    Get a list of final_review_txt_biz_ids by combining all the business 
    ids in all keys from the above dictionary.
    '''
    
    final_review_txts = []
    final_review_txt_biz_ids = []
    reviews = get_reviews_per_biz(
        dataset_path, restaurant_idx, review_limit_per_biz)

    for biz_id in reviews:
        review_txts = []
        review_txt_biz_ids = []
        for review in reviews[biz_id]:
            review_txt = review['text'][:review_len_limit].lower()

            # each line of corpus should be one review
            review_txt = review_txt.replace('\r', '')
            review_txt = review_txt.replace('\n', '')

            if review_expansion_enabled:
                review_txt = expand_review_with_categories(
                    restaurants[restaurant_idx[biz_id]], review_txt)

            # remove the term 'restaurant' from review text and add it to the end of each restaurant
            # this is to avoid 'restaurant' term in the query from affecting ranking
            review_txt = review_txt.replace('restaurants', '')
            review_txt = review_txt.replace('restaurant', '')
            review_txt = review_txt + 'restaurant'

            review_txts.append(review_txt)
            review_txt_biz_ids.append(biz_id)

        if combine_reviews_enabled:
            final_review_txts.append(' '.join(review_txts))
            final_review_txt_biz_ids.append(biz_id)
        else:
            final_review_txts += review_txts
            final_review_txt_biz_ids += review_txt_biz_ids

    return reviews, final_review_txts, final_review_txt_biz_ids


def write_file(filename, data, is_binary_mode=False):
    '''Write given data into a new file with given filename.'''
    if is_binary_mode:
        with open(filename, 'wb') as file:
            file.write(data)
    else:
        with open(filename, 'w', newline='\n', encoding='utf8') as file:
            file.write(data)


def filter_dataset(datastore, dataset_path, review_limit, review_len_limit):
    '''Write restaurants and restaurant_idx returned from function 
    get_overlap_restaurants(dataset_path, datastore.location, 
    yelp_restaurant_biz_id) into new JSON files separately; 

    Write review_txt_biz_ids returned from function get_reviews(
    dataset_path, restaurants, restaurant_idx, review_limit, 
    review_len_limit) into a new text file.

    Create a review.dat file and a line.toml file using review_txts 
    returned from function get_reviews(dataset_path, restaurants, 
    restaurant_idx, review_limit, review_len_limit).
    '''
    print('Getting 1,000 yelp restaurants biz id in ' + datastore.location)
    yelp_restaurant_biz_id = get_restaurant_biz_id_from_yelp(
        datastore.location)

    print('Getting overlapping restaurants...')
    restaurants, restaurant_idx = get_overlap_restaurants(
        dataset_path, datastore.location, yelp_restaurant_biz_id)
    assert len(restaurants) == len(restaurant_idx)

    print('Writing restaurants to file...')
    write_file(datastore.RESTAURANT_DATASET_FILENAME.as_posix(),
               orjson.dumps(restaurants), True)

    print('Writing restaurant index to a file...')
    write_file(datastore.RESTAURANT_INDEX_FILENAME,
               orjson.dumps(restaurant_idx), True)

    print('Getting reviews of the restaurants...this will take some time')
    reviews, review_txts, review_txt_biz_ids = get_reviews(
        dataset_path, restaurants, restaurant_idx, review_limit, review_len_limit)

    n_reviews = 0
    if combine_reviews_enabled:
        assert len(reviews) == len(review_txt_biz_ids)
    else:
        for biz_reviews in [len(reviews[biz_id]) for biz_id in reviews]:
            n_reviews += biz_reviews
        assert len(review_txts) == n_reviews
    assert len(review_txts) == len(review_txt_biz_ids)

    print('Writing review texts to file...this will take some time')
    write_file(datastore.REVIEW_CORPUS_FILENAME.as_posix(),
               '\n'.join(review_txts))

    print('Writing business id associated to the review texts to a file...')
    write_file(datastore.REVIEW_TXT_BIZ_ID_FILENAME,
               '\n'.join(review_txt_biz_ids))

    with open(datastore.REVIEW_CORPUS_FILENAME.as_posix(), 'r', encoding='utf8') as review_corpus:
        print('Checking review corpus length is same as number of reviews in dataset...')
        if combine_reviews_enabled:
            assert len(review_corpus.readlines()) == len(reviews)
        else:
            assert len(review_corpus.readlines()) == n_reviews

    print('Writing review corpus configuration file...')
    write_file(datastore.REVIEW_CORPUS_CFG_FILENAME.as_posix(),
               "type = \"line-corpus\"")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Filter dataset')
    parser.add_argument('-p', '--dataset-dirpath',
                        help='Full dataset path',
                        default='../../yelp_dataset')
    parser.add_argument('--review-limit', type=int, default=100,
                        help='Review limit per restaurant, default=100')
    parser.add_argument('--review-length-limit', type=int,
                        default=5000, help='Review char length limit, default=5000')
    parser.add_argument('--skip-clean', action='store_true',
                        help='Skip cleaning of existing filtered dataset')
    args = parser.parse_args()

    for city_name in CITIES:
        ds = DataStore(city_name)

        dataset_dirpath = Path(args.dataset_dirpath)
        if not Path(args.dataset_dirpath).exists():
            print('Dataset path provided does not exist. Exiting.')
            sys.exit(1)

        ds.create_dir_struct(skip_clean=args.skip_clean)
        filter_dataset(ds, dataset_dirpath,
                       args.review_limit, args.review_length_limit)

    sys.exit(0)

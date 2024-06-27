import pandas as pd
import folium
from heapq import heappop, heappush
from collections import defaultdict

# Load data from the uploaded files
agency = pd.read_csv('../gtfs/agency.txt')
calendar = pd.read_csv('../gtfs/calendar.txt')
calendar_dates = pd.read_csv('../gtfs/calendar_dates.txt')
feed_info = pd.read_csv('../gtfs/feed_info.txt')
routes_df = pd.read_csv('../gtfs/routes.txt')
stops_df = pd.read_csv('../gtfs/stops.txt')
stop_times_df = pd.read_csv('../gtfs/stop_times.txt')
transfers = pd.read_csv('../gtfs/transfers.txt')
trips_df = pd.read_csv('../gtfs/trips.txt')


def normalize_time(t):
    if pd.isna(t):
        return t
    h, m, s = map(int, t.split(':'))
    return pd.Timedelta(hours=h % 24, minutes=m, seconds=s) + pd.Timedelta(days=h // 24)


# Normalize arrival_time and departure_time
stop_times_df['arrival_time'] = stop_times_df['arrival_time'].apply(normalize_time)
stop_times_df['departure_time'] = stop_times_df['departure_time'].apply(normalize_time)

# Merge stop_times with stops to get stop information
stop_times_df = stop_times_df.merge(stops_df, on='stop_id', how='left')

def find_reachable_destinations(city_name, time_limit, max_transfers):
    # Step 1: Identify stop ID(s) for the specified city
    city_stops = stops_df[stops_df['stop_name'].str.contains(city_name, case=False, na=False, regex=False)]
    city_stop_ids = city_stops['stop_id'].tolist()

    # Step 2: Initialize data structures
    priority_queue = [(pd.Timedelta(0), 0, stop_id, city_name) for stop_id in city_stop_ids]
    travel_times = defaultdict(lambda: pd.Timedelta.max)
    transfer_counts = defaultdict(lambda: float('inf'))
    explored_routes = defaultdict(set)
    all_reachable_stops = pd.DataFrame(columns=['stop_id', 'stop_name', 'stop_lat', 'stop_lon', 'travel_time', 'transfer_count'])

    for stop_id in city_stop_ids:
        travel_times[(stop_id, 0)] = pd.Timedelta(0)
        transfer_counts[(stop_id, 0)] = 0

    while priority_queue:
        current_time, transfers, current_stop, origin_city = heappop(priority_queue)

        if transfers > max_transfers or current_time > time_limit:
            continue

        next_trips = stop_times_df[stop_times_df['stop_id'] == current_stop]['trip_id'].unique()

        for trip_id in next_trips:
            if trip_id in explored_routes[origin_city]:
                continue
            explored_routes[origin_city].add(trip_id)

            trip_stop_times = stop_times_df[stop_times_df['trip_id'] == trip_id].sort_values('stop_sequence').reset_index(drop=True)
            start_index = trip_stop_times[trip_stop_times['stop_id'] == current_stop].index[0]

            cumulative_travel_time = current_time

            for i in range(start_index + 1, len(trip_stop_times)):
                prev_stop = trip_stop_times.iloc[i - 1]
                next_stop = trip_stop_times.iloc[i]
                travel_time = next_stop['arrival_time'] - prev_stop['departure_time']
                cumulative_travel_time += travel_time

                if cumulative_travel_time > time_limit:
                    break

                next_stop_id = next_stop['stop_id']
                if (next_stop_id, transfers) not in travel_times or cumulative_travel_time < travel_times[(next_stop_id, transfers)]:
                    travel_times[(next_stop_id, transfers)] = cumulative_travel_time
                    transfer_counts[(next_stop_id, transfers)] = transfers
                    heappush(priority_queue, (cumulative_travel_time, transfers, next_stop_id, origin_city))

                    if transfers < max_transfers:
                        heappush(priority_queue, (cumulative_travel_time, transfers + 1, next_stop_id, next_stop['stop_name']))

                    if next_stop_id not in all_reachable_stops['stop_id'].values:
                        all_reachable_stops = pd.concat([all_reachable_stops, pd.DataFrame({
                            'stop_id': [next_stop_id],
                            'stop_name': [next_stop['stop_name']],
                            'stop_lat': [next_stop['stop_lat']],
                            'stop_lon': [next_stop['stop_lon']],
                            'travel_time': [cumulative_travel_time],
                            'transfer_count': [transfers]
                        })])
        print(all_reachable_stops)

    return all_reachable_stops


# Example usage for multi-level reachable destinations:
city_name = "Budapest"
max_transfers = 0  # Specify the maximum number of transfers
time_limit = pd.Timedelta(hours=5)  # Specify the time limit
reachable_stops_info = find_reachable_destinations(city_name, time_limit, max_transfers)

def visualize_reachable_destinations(city_name, reachable_stops_info):
    # Get coordinates for the specified city
    city_coords = stops_df[stops_df['stop_name'].str.contains(city_name, case=False, na=False, regex=False)][['stop_lat', 'stop_lon']].values[0].tolist()

    # Create a map centered around the specified city
    map_city = folium.Map(location=city_coords, zoom_start=6)

    # Add markers for reachable stops
    for _, row in reachable_stops_info.iterrows():
        stop_coords = [row['stop_lat'], row['stop_lon']]
        if row['transfer_count'] == 0:
            popup_info = f"Direct: {row['stop_name']}<br>Travel Time: {row['travel_time']}"
            folium.Marker(location=stop_coords, popup=popup_info, icon=folium.Icon(color='green')).add_to(map_city)
        else:
            popup_info = f"{row['transfer_count']} Transfers: {row['stop_name']}<br>Travel Time: {row['travel_time']}"
            folium.Marker(location=stop_coords, popup=popup_info, icon=folium.Icon(color='blue')).add_to(map_city)

    map_path = f'all_reachable_from_{city_name.lower()}_map.html'
    map_city.save(map_path)

    return map_city

# Example usage for visualization:
map_city = visualize_reachable_destinations(city_name, reachable_stops_info)

import React, { useState, useEffect } from 'react';
import { View, Text, FlatList, ActivityIndicator, SafeAreaView, RefreshControl, TouchableOpacity, Platform } from 'react-native';
import axios from 'axios';
import { io } from 'socket.io-client';
import DateTimePicker from '@react-native-community/datetimepicker';

const API_URL = 'http://10.0.2.2:8000/api'; // Android Emulator localhost
const WS_URL = 'ws://10.0.2.2:8000/ws/prices';

export default function LivePricesScreen() {
  const [prices, setPrices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [date, setDate] = useState(new Date());
  const [showPicker, setShowPicker] = useState(false);

  const fetchPrices = async (selectedDate = date) => {
    try {
      const formattedDate = selectedDate.toISOString().split('T')[0];
      const response = await axios.get(`${API_URL}/prices?category=flower&date=${formattedDate}`);
      if (response.data.status === 'success') {
        setPrices(response.data.data);
      }
    } catch (error) {
      console.error("Error fetching prices:", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchPrices();

    // Setup WebSocket connection for real-time updates
    const socket = new WebSocket(WS_URL);
    
    socket.onopen = () => {
      console.log("WebSocket connected");
    };
    
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (Array.isArray(data)) {
            setPrices(data);
        } else {
            fetchPrices();
        }
      } catch (e) {
        console.error("Error parsing websocket message", e);
      }
    };

    return () => {
      socket.close();
    };
  }, []); // Re-run websocket connection is not needed on date change, but fetchPrices is called manually.

  const onRefresh = () => {
    setRefreshing(true);
    fetchPrices();
  };

  const onDateChange = (event, selectedDate) => {
    const currentDate = selectedDate || date;
    setShowPicker(Platform.OS === 'ios');
    setDate(currentDate);
    if (event.type === 'set' || Platform.OS === 'ios') {
        setLoading(true);
        fetchPrices(currentDate);
    }
  };

  const renderItem = ({ item }) => (
    <View className="bg-white p-4 mb-3 rounded-lg shadow-sm border border-gray-100 flex-row justify-between items-center">
      <View className="flex-1">
        <Text className="text-lg font-bold text-dark">{item.commodity}</Text>
        <Text className="text-sm text-gray-500">{item.market || item.city} • {item.district}</Text>
        <Text className="text-xs text-gray-400 mt-1">Updated: {item.date}</Text>
      </View>
      <View className="items-end">
        <Text className="text-xl font-extrabold text-primary">₹{item.price}</Text>
        <Text className="text-xs text-gray-500">per {item.unit || 'Kg'}</Text>
      </View>
    </View>
  );

  return (
    <SafeAreaView className="flex-1 bg-light">
      <View className="p-4 bg-white shadow-sm border-b border-gray-200 flex-row justify-between items-center">
         <Text className="text-lg font-bold text-gray-800">Historical Prices</Text>
         <TouchableOpacity 
            onPress={() => setShowPicker(true)}
            className="bg-primary px-4 py-2 rounded-full"
         >
            <Text className="text-white font-semibold text-sm">
                {date.toISOString().split('T')[0]} 📅
            </Text>
         </TouchableOpacity>
      </View>

      {showPicker && (
        <DateTimePicker
          testID="dateTimePicker"
          value={date}
          mode="date"
          is24Hour={true}
          display="default"
          onChange={onDateChange}
        />
      )}

      {loading ? (
        <View className="flex-1 justify-center items-center">
          <ActivityIndicator size="large" color="#16a34a" />
        </View>
      ) : (
        <FlatList
          data={prices}
          keyExtractor={(item, index) => item._id || index.toString()}
          renderItem={renderItem}
          contentContainerStyle={{ padding: 16 }}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={["#16a34a"]} />
          }
          ListEmptyComponent={
            <View className="flex-1 justify-center items-center py-10">
              <Text className="text-gray-500 text-lg">No prices available for this date.</Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

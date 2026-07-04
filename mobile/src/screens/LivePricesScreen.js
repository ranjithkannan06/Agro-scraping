import React, { useState, useEffect, useRef } from 'react';
import { View, Text, FlatList, ActivityIndicator, SafeAreaView, RefreshControl, TouchableOpacity, Platform, TextInput, Animated } from 'react-native';
import axios from 'axios';
import { io } from 'socket.io-client';
import DateTimePicker from '@react-native-community/datetimepicker';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';

const API_URL = 'http://10.178.10.188:8000/api'; // Android Emulator localhost
const WS_URL = 'ws://10.178.10.188:8000/ws/prices';

export default function LivePricesScreen() {
  const [prices, setPrices] = useState([]);
  const [filteredPrices, setFilteredPrices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [date, setDate] = useState(new Date());
  const [showPicker, setShowPicker] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchPrices = async (selectedDate = date) => {
    try {
      const formattedDate = selectedDate.toISOString().split('T')[0];
      const response = await axios.get(`${API_URL}/prices?category=flower&date=${formattedDate}`);
      if (response.data.status === 'success') {
        setPrices(response.data.data);
        setFilteredPrices(response.data.data);
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

    const socket = new WebSocket(WS_URL);
    
    socket.onopen = () => {
      console.log("WebSocket connected");
    };
    
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (Array.isArray(data)) {
            setPrices(data);
            setFilteredPrices(data); // In a real app, re-apply filter here
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
  }, []);

  useEffect(() => {
    if (searchQuery) {
      const lowerQuery = searchQuery.toLowerCase();
      const filtered = prices.filter(p => 
        (p.commodity && p.commodity.toLowerCase().includes(lowerQuery)) ||
        (p.market && p.market.toLowerCase().includes(lowerQuery)) ||
        (p.district && p.district.toLowerCase().includes(lowerQuery))
      );
      setFilteredPrices(filtered);
    } else {
      setFilteredPrices(prices);
    }
  }, [searchQuery, prices]);

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

  const AnimatedListItem = ({ item, index }) => {
    const animValue = useRef(new Animated.Value(0)).current;
    const hasAnimated = useRef(false);

    useEffect(() => {
      if (!hasAnimated.current) {
        Animated.timing(animValue, {
          toValue: 1,
          duration: 400,
          delay: Math.min(index * 50, 500),
          useNativeDriver: true,
        }).start(() => {
          hasAnimated.current = true;
        });
      }
    }, [index]); // Re-run animation if item index somehow changes, though key ensures stability

    const animStyle = {
      opacity: animValue,
      transform: [{
        translateY: animValue.interpolate({
          inputRange: [0, 1],
          outputRange: [30, 0]
        })
      }]
    };

    return (
      <Animated.View style={animStyle} className="bg-white p-4 mb-3 rounded-2xl shadow-sm border border-gray-100 flex-row justify-between items-center">
        <View className="flex-row items-center flex-1">
          <View className="bg-green-100 p-3 rounded-full mr-3">
            <MaterialCommunityIcons name="flower" size={24} color="#16a34a" />
          </View>
          <View className="flex-1">
            <Text className="text-lg font-bold text-dark">{item.commodity}</Text>
            <Text className="text-sm text-gray-500">{item.market || item.city} • {item.district}</Text>
            <Text className="text-xs text-gray-400 mt-1">Updated: {item.date}</Text>
          </View>
        </View>
        <View className="items-end pl-2">
          <Text className="text-xl font-extrabold text-primary">₹{item.price}</Text>
          <Text className="text-xs text-gray-500">per {item.unit || 'Kg'}</Text>
        </View>
      </Animated.View>
    );
  };

  const renderItem = ({ item, index }) => <AnimatedListItem item={item} index={index} />;

  return (
    <SafeAreaView className="flex-1 bg-light">
      <View className="p-4 bg-white shadow-sm z-10">
         <View className="flex-row justify-between items-center mb-4">
            <Text className="text-2xl font-bold text-dark">Market Prices</Text>
            <TouchableOpacity 
                onPress={() => setShowPicker(true)}
                className="bg-primary/10 px-4 py-2 rounded-full flex-row items-center"
            >
                <Feather name="calendar" size={16} color="#16a34a" />
                <Text className="text-primary font-bold text-sm ml-2">
                    {date.toISOString().split('T')[0]}
                </Text>
            </TouchableOpacity>
         </View>
         
         <View className="flex-row items-center bg-gray-100 rounded-xl px-4 py-3">
            <Feather name="search" size={20} color="gray" />
            <TextInput 
              placeholder="Search by commodity, market..."
              className="flex-1 ml-3 text-base text-dark"
              value={searchQuery}
              onChangeText={setSearchQuery}
              placeholderTextColor="gray"
            />
            {searchQuery.length > 0 && (
              <TouchableOpacity onPress={() => setSearchQuery('')}>
                <Feather name="x-circle" size={20} color="gray" />
              </TouchableOpacity>
            )}
         </View>
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
          data={filteredPrices}
          keyExtractor={(item, index) => item._id || index.toString()}
          renderItem={renderItem}
          initialNumToRender={10}
          windowSize={5}
          contentContainerStyle={{ padding: 16, paddingTop: 8 }}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={["#16a34a"]} />
          }
          ListEmptyComponent={
            <View className="flex-1 justify-center items-center py-20 mt-10">
              <MaterialCommunityIcons name="emoticon-sad-outline" size={64} color="#d1d5db" />
              <Text className="text-gray-500 text-lg mt-4 font-medium text-center">
                {searchQuery ? "No matching prices found." : "No prices available for this date."}
              </Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}


import React, { useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, SafeAreaView, ScrollView, Animated } from 'react-native';
import { Ionicons, MaterialCommunityIcons, Feather } from '@expo/vector-icons';

const ActionCard = ({ title, icon, onPress, bgColor, animStyle }) => (
  <Animated.View style={[{ width: '48%', marginBottom: 16 }, animStyle]}>
    <TouchableOpacity 
      onPress={onPress}
      className="p-4 rounded-2xl shadow-sm flex-col justify-between h-full"
      style={{ backgroundColor: bgColor || 'white' }}
    >
      <View className="mb-3">
        {icon}
      </View>
      <Text className="text-dark font-bold text-lg">{title}</Text>
    </TouchableOpacity>
  </Animated.View>
);

export default function HomeScreen({ navigation }) {
  const slideAnims = useRef([...Array(4)].map(() => new Animated.Value(0))).current;

  useEffect(() => {
    const animations = slideAnims.map((anim) => 
      Animated.timing(anim, {
        toValue: 1,
        duration: 400,
        useNativeDriver: true,
      })
    );
    Animated.stagger(100, animations).start();
  }, []);

  const getAnimStyle = (index) => ({
    opacity: slideAnims[index],
    transform: [{
      translateY: slideAnims[index].interpolate({
        inputRange: [0, 1],
        outputRange: [30, 0]
      })
    }]
  });

  return (
    <SafeAreaView className="flex-1 bg-light">
      <ScrollView className="flex-1" showsVerticalScrollIndicator={false}>
        {/* Header Section */}
        <View className="px-6 pt-6 pb-4 bg-primary rounded-b-[30px]">
          <View className="flex-row justify-between items-center mb-6">
            <View>
              <Text className="text-white/80 text-sm font-medium mb-1">Good Morning,</Text>
              <Text className="text-white text-2xl font-bold">Ranjith 👋</Text>
            </View>
            <TouchableOpacity className="bg-white/20 p-2 rounded-full">
              <Ionicons name="notifications-outline" size={24} color="white" />
            </TouchableOpacity>
          </View>
          
          {/* Weather Widget */}
          <View className="bg-white/10 p-4 rounded-2xl flex-row items-center justify-between">
            <View className="flex-row items-center">
              <Feather name="sun" size={32} color="#facc15" />
              <View className="ml-3">
                <Text className="text-white font-bold text-lg">28°C</Text>
                <Text className="text-white/80 text-sm">Sunny • Chennai</Text>
              </View>
            </View>
            <Text className="text-white/90 text-sm font-medium">AQI: 42</Text>
          </View>
        </View>

        <View className="px-5 pt-6">
          <Text className="text-xl font-bold text-dark mb-4">Quick Actions</Text>
          
          <View className="flex-row flex-wrap justify-between">
            <ActionCard 
              title="Live Market"
              icon={<MaterialCommunityIcons name="storefront-outline" size={32} color="#16a34a" />}
              onPress={() => navigation.navigate('Market')}
              bgColor="#dcfce7"
              animStyle={getAnimStyle(0)}
            />
            <ActionCard 
              title="Crop Advisor"
              icon={<MaterialCommunityIcons name="leaf-outline" size={32} color="#0284c7" />}
              onPress={() => console.log('Crop Advisor')}
              bgColor="#e0f2fe"
              animStyle={getAnimStyle(1)}
            />
            <ActionCard 
              title="My Farm"
              icon={<Ionicons name="map-outline" size={32} color="#d97706" />}
              onPress={() => console.log('My Farm')}
              bgColor="#fef3c7"
              animStyle={getAnimStyle(2)}
            />
            <ActionCard 
              title="Schemes"
              icon={<Ionicons name="document-text-outline" size={32} color="#9333ea" />}
              onPress={() => console.log('Govt Schemes')}
              bgColor="#f3e8ff"
              animStyle={getAnimStyle(3)}
            />
          </View>

          <View className="mt-6 mb-8">
             <View className="flex-row justify-between items-center mb-4">
                <Text className="text-xl font-bold text-dark">Trending Prices</Text>
                <TouchableOpacity onPress={() => navigation.navigate('Market')}>
                   <Text className="text-primary font-semibold">See All</Text>
                </TouchableOpacity>
             </View>
             
             {/* Dummy Trending Card */}
             <View className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex-row justify-between items-center mb-3">
               <View className="flex-row items-center">
                 <View className="bg-orange-100 p-3 rounded-full mr-3">
                    <MaterialCommunityIcons name="flower" size={24} color="#ea580c" />
                 </View>
                 <View>
                   <Text className="font-bold text-dark text-lg">Jasmine</Text>
                   <Text className="text-gray-500 text-sm">Coimbatore Market</Text>
                 </View>
               </View>
               <View className="items-end">
                 <Text className="font-extrabold text-primary text-lg">₹450</Text>
                 <View className="flex-row items-center mt-1">
                    <Feather name="trending-up" size={14} color="#16a34a" />
                    <Text className="text-primary text-xs ml-1 font-semibold">+5%</Text>
                 </View>
               </View>
             </View>

             <View className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex-row justify-between items-center">
               <View className="flex-row items-center">
                 <View className="bg-yellow-100 p-3 rounded-full mr-3">
                    <MaterialCommunityIcons name="flower" size={24} color="#ca8a04" />
                 </View>
                 <View>
                   <Text className="font-bold text-dark text-lg">Marigold</Text>
                   <Text className="text-gray-500 text-sm">Madurai Market</Text>
                 </View>
               </View>
               <View className="items-end">
                 <Text className="font-extrabold text-primary text-lg">₹60</Text>
                 <View className="flex-row items-center mt-1">
                    <Feather name="trending-down" size={14} color="#dc2626" />
                    <Text className="text-red-600 text-xs ml-1 font-semibold">-2%</Text>
                 </View>
               </View>
             </View>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

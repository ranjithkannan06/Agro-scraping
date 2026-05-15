import React from 'react';
import { View, Text, TouchableOpacity, SafeAreaView } from 'react-native';

export default function HomeScreen({ navigation }) {
  return (
    <SafeAreaView className="flex-1 bg-light">
      <View className="flex-1 justify-center items-center p-4">
        <Text className="text-3xl font-bold text-primary mb-2">Welcome to</Text>
        <Text className="text-4xl font-extrabold text-dark mb-8">Athanur Agro</Text>
        
        <View className="w-full space-y-4">
          <TouchableOpacity 
            className="bg-primary p-4 rounded-xl shadow-sm"
            onPress={() => navigation.navigate('LivePrices')}
          >
            <Text className="text-white text-center text-lg font-semibold">
              View Live Flower Prices
            </Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            className="bg-white border-2 border-primary p-4 rounded-xl shadow-sm mt-4"
            onPress={() => console.log('Navigate to Marketplace')}
          >
            <Text className="text-primary text-center text-lg font-semibold">
              Marketplace (Coming Soon)
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );
}

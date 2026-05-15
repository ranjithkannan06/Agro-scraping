import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import HomeScreen from '../screens/HomeScreen';
import LivePricesScreen from '../screens/LivePricesScreen';

const Stack = createNativeStackNavigator();

export default function AppNavigator() {
  return (
    <NavigationContainer>
      <Stack.Navigator 
        initialRouteName="Home"
        screenOptions={{
          headerStyle: {
            backgroundColor: '#16a34a',
          },
          headerTintColor: '#fff',
          headerTitleStyle: {
            fontWeight: 'bold',
          },
        }}
      >
        <Stack.Screen 
          name="Home" 
          component={HomeScreen} 
          options={{ title: 'HarvestHub' }}
        />
        <Stack.Screen 
          name="LivePrices" 
          component={LivePricesScreen} 
          options={{ title: 'Live Flower Prices' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

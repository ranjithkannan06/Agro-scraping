import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import AppNavigator from './src/navigation/AppNavigator';
import { useEffect, useRef, useState, useCallback } from 'react';
import * as Notifications from 'expo-notifications';
import { registerForPushNotificationsAsync } from './src/utils/notifications';
import axios from 'axios';
import * as ExpoSplashScreen from 'expo-splash-screen';
import SplashScreen from './src/components/SplashScreen';
import { View } from 'react-native';

const API_URL = 'http://10.178.10.188:8000/api';

// Keep the native splash screen visible while we initialize
ExpoSplashScreen.preventAutoHideAsync();

export default function App() {
  const [expoPushToken, setExpoPushToken] = useState('');
  const [appIsReady, setAppIsReady] = useState(false);
  const [showSplash, setShowSplash] = useState(true);
  const notificationListener = useRef();
  const responseListener = useRef();

  useEffect(() => {
    async function prepare() {
      try {
        // Pre-load fonts, make any API calls you need to do here
        const token = await registerForPushNotificationsAsync();
        if (token) {
          setExpoPushToken(token);
          axios.post(`${API_URL}/notifications/token`, { token })
            .then(() => console.log('Token registered with backend'))
            .catch(err => console.error('Failed to register token:', err));
        }
      } catch (e) {
        console.warn(e);
      } finally {
        // Tell the application to render
        setAppIsReady(true);
      }
    }

    prepare();

    notificationListener.current = Notifications.addNotificationReceivedListener(notification => {
      console.log('Received notification:', notification);
    });

    responseListener.current = Notifications.addNotificationResponseReceivedListener(response => {
      console.log('Clicked notification:', response);
    });

    return () => {
      Notifications.removeNotificationSubscription(notificationListener.current);
      Notifications.removeNotificationSubscription(responseListener.current);
    };
  }, []);

  const onLayoutRootView = useCallback(async () => {
    if (appIsReady) {
      // Hide the native splash screen when our root view renders
      await ExpoSplashScreen.hideAsync();
    }
  }, [appIsReady]);

  if (!appIsReady) {
    return null;
  }

  return (
    <SafeAreaProvider onLayout={onLayoutRootView}>
      <View style={{ flex: 1 }}>
        <AppNavigator />
        {showSplash && <SplashScreen onFinish={() => setShowSplash(false)} />}
      </View>
      <StatusBar style="auto" />
    </SafeAreaProvider>
  );
}

import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import Constants from 'expo-constants';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPushNotificationsAsync() {
  let token;

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'default',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#16a34a',
    });
  }

  if (Device.isDevice) {
    // In SDK 53+, Expo Go no longer supports Push Notifications.
    // We must bypass it to prevent the app from crashing on the red screen.
    const isExpoGo = typeof expo !== 'undefined' && expo?.modules?.ExpoGo !== undefined;
    if (isExpoGo || (Constants && Constants.appOwnership === 'expo')) {
      console.log('Push notifications are not supported in Expo Go for SDK 53+. Skipping token generation.');
      return 'dummy-token-expo-go';
    }

    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;
    if (existingStatus !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    if (finalStatus !== 'granted') {
      console.log('Failed to get push token for push notification!');
      return null;
    }
    try {
        const projectId = 'your-eas-project-id'; 
        token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
        console.log("Expo Push Token:", token);
    } catch (e) {
        // Change from console.error to console.log to avoid the Red Screen of Death
        console.log("Push notification token fetch bypassed:", e.message);
    }
  } else {
    console.log('Must use physical device for Push Notifications');
  }

  return token;
}

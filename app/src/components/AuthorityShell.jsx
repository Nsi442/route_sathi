import ConsoleShell from './ConsoleShell';
import { IconChart, IconDashboard, IconList, IconWrench } from './Icons';

const NAV = [
  { to: '/authority', label: 'Overview', end: true, icon: <IconDashboard width={18} height={18} /> },
  { to: '/authority/reports', label: 'Reports', icon: <IconList width={18} height={18} /> },
  { to: '/authority/maintenance', label: 'Maintenance', icon: <IconWrench width={18} height={18} /> },
  { to: '/authority/analytics', label: 'Map & Analytics', icon: <IconChart width={18} height={18} /> },
];

export default function AuthorityShell(props) {
  return <ConsoleShell portal="Authority Portal" navItems={NAV} {...props} />;
}

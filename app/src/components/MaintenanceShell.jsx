import ConsoleShell from './ConsoleShell';
import { IconCheck, IconDashboard, IconWrench } from './Icons';

const NAV = [
  { to: '/maintenance', label: 'My Tasks', end: true, icon: <IconDashboard width={18} height={18} /> },
  { to: '/maintenance/active', label: 'In Progress', icon: <IconWrench width={18} height={18} /> },
  { to: '/maintenance/completed', label: 'Completed', icon: <IconCheck width={18} height={18} /> },
];

export default function MaintenanceShell(props) {
  return <ConsoleShell portal="Maintenance Portal" navItems={NAV} {...props} />;
}

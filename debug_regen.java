import java.text.SimpleDateFormat;
import java.util.Date;

protected void log(String message) {
    SimpleDateFormat sdf = new SimpleDateFormat("HH:mm:ss");
    String timestamp = sdf.format(new Date());
    System.out.println(timestamp + " - " + message);
}
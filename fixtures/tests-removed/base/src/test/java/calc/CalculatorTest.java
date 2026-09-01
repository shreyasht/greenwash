package calc;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

class CalculatorTest {
    @Test
    void addsTwoNumbers() {
        assertEquals(5, new Calculator().add(2, 3));
    }

    @Test
    void addsZero() {
        assertEquals(0, new Calculator().add(0, 0));
    }
}
